from decimal import Decimal
import hashlib
import hmac
import os
import urllib.parse
from uuid import UUID

from django.contrib.auth import authenticate, get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models import Q
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Address, UserRole
from apps.catalog.models import Category, Product, ProductImage, Variant
from apps.catalog.serializers import ProductSerializer
from apps.inventory.models import Inventory
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.payments.models import Payment, PaymentStatus
from apps.sellers.models import SellerProfile, VerificationStatus
from apps.node_compat.models import GuestCart

User = get_user_model()


def token_for(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def user_data(user):
    return {'id': str(user.id), 'name': user.get_full_name() or user.username,
            'email': user.email, 'phone': user.phone_number, 'role': user.role,
            'shopName': getattr(getattr(user, 'seller_profile', None), 'business_name', None),
            'isSellerApproved': getattr(getattr(user, 'seller_profile', None), 'verification_status', '') == 'APPROVED'}


def node_response(data=None, message='Success', code=200, **extra):
    body = {'success': 200 <= code < 300, 'statusCode': code, 'message': message, 'data': data}
    body.update(extra)
    return Response(body, status=code)


def clean_image_path(img_src):
    if not img_src:
        return ""
    s = urllib.parse.unquote(str(img_src)).strip()
    if not s:
        return ""

    if '/assets/' in s:
        asset_rel = s.split('/assets/')[-1]
        return f"/assets/{asset_rel}"
    if s.startswith('/assets/'):
        return s

    if '?' in s:
        s = s.split('?')[0]

    if '/media/' in s:
        s = s.split('/media/')[-1]

    if s.startswith('http://') or s.startswith('https://'):
        if 'product_images/' in s:
            s = 'product_images/' + s.split('product_images/')[-1]
        elif 'products/' in s:
            s = 'products/' + s.split('products/')[-1]
        else:
            parts = s.split('/')
            if len(parts) > 3:
                s = '/'.join(parts[3:])

    return urllib.parse.unquote(s).lstrip('/')[:450]


def sync_product_variants(product, v_list, product_image_fallback=None):
    if not isinstance(v_list, list):
        return []

    # Build color image map and color hex map across all input variants
    color_image_map = {}
    color_hex_map = {}
    for v_item in v_list:
        if not isinstance(v_item, dict):
            continue
        v_color = str(v_item.get('color', '') or '').strip()
        v_color_key = v_color.lower()
        v_hex = str(v_item.get('colorHex') or v_item.get('color_hex') or '').strip()
        if v_color_key and v_hex and v_hex != '#B8963E':
            color_hex_map[v_color_key] = v_hex

        if v_color_key:
            raw_v_imgs = [
                clean_image_path(k) for k in v_item.get('imageKeys', []) if k
            ] + [
                clean_image_path(u) for u in v_item.get('images', []) if u
            ]
            v_imgs = list(dict.fromkeys([img for img in raw_v_imgs if img]))
            if v_imgs:
                if v_color_key not in color_image_map:
                    color_image_map[v_color_key] = []
                for img in v_imgs:
                    if img not in color_image_map[v_color_key]:
                        color_image_map[v_color_key].append(img)

    kept_variant_ids = []
    created_or_updated = []
    for v_item in v_list:
        if not isinstance(v_item, dict):
            continue
        sku = (v_item.get('sku') or '').strip()
        v_id = v_item.get('id')
        selling_price = Decimal(str(v_item.get('price', 0) or 0))
        regular_price = Decimal(str(v_item.get('originalPrice', selling_price) or selling_price))
        v_size = str(v_item.get('size', '') or '').strip()
        v_color = str(v_item.get('color', '') or '').strip()
        v_color_key = v_color.lower()
        
        v_hex = str(v_item.get('colorHex') or v_item.get('color_hex') or '').strip()
        if not v_hex or v_hex == '#B8963E':
            v_hex = color_hex_map.get(v_color_key) or str(product.color_hex or '#B8963E').strip()

        variant = None
        if v_id:
            try:
                variant = Variant.objects.filter(id=v_id, product=product).first()
            except Exception:
                variant = None
        if not variant and sku:
            variant = Variant.objects.filter(sku=sku, product=product).first()
        if not variant and (v_size or v_color):
            variant = Variant.objects.filter(product=product, size__iexact=v_size, color__iexact=v_color).first()

        if not sku:
            color_code = v_color[:3].upper() if v_color else 'VAR'
            size_code = v_size.upper() if v_size else 'FREE'
            sku = f"SKU-{slugify(product.name)[:10].upper()}-{color_code}-{size_code}-{str(UUID(int=__import__('uuid').uuid4().int))[:4]}"

        if variant:
            variant.size = v_size
            variant.color = v_color
            variant.color_hex = v_hex
            variant.price = regular_price
            variant.discount_price = selling_price if selling_price < regular_price else None
            if sku and not Variant.objects.filter(sku=sku).exclude(id=variant.id).exists():
                variant.sku = sku
            variant.save()
        else:
            if Variant.objects.filter(sku=sku).exists():
                sku = f"{sku}-{str(UUID(int=__import__('uuid').uuid4().int))[:4]}"
            variant = Variant.objects.create(
                product=product,
                sku=sku,
                size=v_size,
                color=v_color,
                color_hex=v_hex,
                price=regular_price,
                discount_price=selling_price if selling_price < regular_price else None
            )

        kept_variant_ids.append(variant.id)
        created_or_updated.append(variant)

        stock_qty = int(v_item.get('stock', 0) or 0)
        inventory, _ = Inventory.objects.get_or_create(variant=variant)
        inventory.available_stock = max(0, stock_qty)
        inventory.save()

        raw_var_images = [
            clean_image_path(k) for k in v_item.get('imageKeys', []) if k
        ] + [
            clean_image_path(u) for u in v_item.get('images', []) if u
        ]
        var_images = list(dict.fromkeys([img for img in raw_var_images if img]))
        
        # Color level image fallback (Myntra-style: size variants inherit color images)
        if not var_images and v_color_key in color_image_map:
            var_images = color_image_map[v_color_key]

        if var_images:
            ProductImage.objects.filter(variant=variant).delete()
            for img_src in var_images:
                c = clean_image_path(img_src)
                if c:
                    ProductImage.objects.create(variant=variant, image=c)
        elif product_image_fallback and not variant.images.exists():
            for img_src in product_image_fallback:
                c = clean_image_path(img_src)
                if c:
                    ProductImage.objects.create(variant=variant, image=c)

    if kept_variant_ids:
        Variant.objects.filter(product=product).exclude(id__in=kept_variant_ids).delete()

    return created_or_updated


def sync_product_group_colors(main_product, variants_input, product_image_sources=None):
    if not isinstance(variants_input, list) or len(variants_input) == 0:
        return [main_product]

    if not main_product.group_id:
        main_product.group_id = f"STYLE-{slugify(main_product.name)[:15].upper()}-{str(UUID(int=__import__('uuid').uuid4().int))[:6]}"
        main_product.save(update_fields=['group_id'])

    color_groups = {}
    for v_item in variants_input:
        if not isinstance(v_item, dict):
            continue
        c_name = str(v_item.get('color') or '').strip()
        c_key = c_name.lower() or 'default'
        if c_key not in color_groups:
            color_groups[c_key] = {
                'color_name': c_name,
                'color_hex': str(v_item.get('colorHex') or v_item.get('color_hex') or '#B8963E').strip(),
                'variants': []
            }
        color_groups[c_key]['variants'].append(v_item)

    color_keys = list(color_groups.keys())
    if not color_keys:
        sync_product_variants(main_product, variants_input, product_image_sources)
        return [main_product]

    primary_key = color_keys[0]
    primary_group = color_groups[primary_key]
    main_product.color_name = primary_group['color_name']
    main_product.color_hex = primary_group['color_hex']
    main_product.save(update_fields=['color_name', 'color_hex'])
    sync_product_variants(main_product, primary_group['variants'], product_image_sources)

    existing_siblings = list(Product.objects.filter(group_id=main_product.group_id).exclude(id=main_product.id))
    sibling_map = { (p.color_name or '').strip().lower(): p for p in existing_siblings }

    all_products = [main_product]

    for c_key in color_keys[1:]:
        c_data = color_groups[c_key]
        c_name = c_data['color_name']
        c_hex = c_data['color_hex']
        
        sib_product = sibling_map.get(c_key)
        if not sib_product:
            sib_product = Product.objects.create(
                seller=main_product.seller,
                category=main_product.category,
                name=main_product.name,
                slug=f"{slugify(main_product.name)}-{slugify(c_name)}-{str(UUID(int=__import__('uuid').uuid4().int))[:6]}",
                description=main_product.description,
                group_id=main_product.group_id,
                color_name=c_name,
                color_hex=c_hex,
                product_type=main_product.product_type,
                is_active=main_product.is_active
            )
        else:
            sib_product.name = main_product.name
            sib_product.description = main_product.description
            sib_product.category = main_product.category
            sib_product.color_name = c_name
            sib_product.color_hex = c_hex
            sib_product.product_type = main_product.product_type
            sib_product.is_active = main_product.is_active
            sib_product.save()

        sync_product_variants(sib_product, c_data['variants'], product_image_sources)
        all_products.append(sib_product)

    Product.objects.filter(group_id=main_product.group_id).exclude(id__in=[p.id for p in all_products]).delete()
    return all_products



def product_data(request, product):
    variants = list(product.variants.select_related('inventory').prefetch_related('images').all())
    first = variants[0] if variants else None
    stock = sum(getattr(getattr(v, 'inventory', None), 'available_stock', 0) for v in variants)
    
    def format_img_url(img_obj):
        if not img_obj:
            return ""
        img_str = str(img_obj).strip()
        if not img_str:
            return ""
        if img_str.startswith('/assets/') or img_str.startswith('assets/'):
            if not img_str.startswith('/'):
                return '/' + img_str
            return img_str
        
        clean_key = clean_image_path(img_str)
        if not clean_key:
            return ""

        try:
            url = default_storage.url(clean_key)
            if url.startswith('http://') or url.startswith('https://'):
                return url
            return request.build_absolute_uri(url)
        except Exception:
            pass

        if '/media/' in clean_key:
            clean_rel = clean_key.split('/media/')[-1]
            return request.build_absolute_uri('/media/' + clean_rel)
        clean_rel = clean_key.lstrip('/')
        return request.build_absolute_uri('/media/' + clean_rel)

    main_images = []
    for v in variants:
        for i in v.images.all():
            formatted = format_img_url(i.image)
            if formatted and formatted not in main_images:
                main_images.append(formatted)

    if not main_images:
        main_images = ["/assets/1540aab590cd7d478ad01cdb1a615d469ef2a808.png"]

    variant_data = []
    for v in variants:
        v_images = [format_img_url(i.image) for i in v.images.all() if format_img_url(i.image)]
        if not v_images:
            v_images = main_images
        v_price = float(v.discount_price or v.price) if v.price else 0.0
        v_orig = float(v.price) if v.price else 0.0
        v_disc_pct = round(((v_orig - v_price) / v_orig) * 100) if v_orig > v_price and v_orig > 0 else 0
        v_stock = getattr(getattr(v, 'inventory', None), 'available_stock', 0)
        variant_data.append({
            'id': str(v.id),
            'sku': v.sku,
            'size': v.size,
            'color': v.color,
            'colorHex': getattr(v, 'color_hex', '') or product.color_hex or '#B8963E',
            'price': v_price,
            'originalPrice': v_orig,
            'discountPercent': v_disc_pct,
            'stock': v_stock,
            'images': v_images,
            'image': v_images[0] if v_images else main_images[0],
            'available_stock': v_stock
        })

    colors = []
    seen_colors = {}
    for v in variants:
        if v.color:
            v_hex = getattr(v, 'color_hex', '') or product.color_hex or '#B8963E'
            v_stock = getattr(getattr(v, 'inventory', None), 'available_stock', 0)
            if v.color not in seen_colors:
                seen_colors[v.color] = {
                    'name': v.color,
                    'hex': v_hex,
                    'colorHex': v_hex,
                    'inStock': v_stock > 0
                }
            else:
                if v_hex and v_hex != '#B8963E':
                    seen_colors[v.color]['hex'] = v_hex
                    seen_colors[v.color]['colorHex'] = v_hex
                if v_stock > 0:
                    seen_colors[v.color]['inStock'] = True

    colors = list(seen_colors.values())

    first_price = float(first.discount_price or first.price) if first and first.price else 0.0
    first_orig = float(first.price) if first and first.price else 0.0

    color_variants = []
    if getattr(product, 'group_id', None):
        siblings = Product.objects.filter(group_id=product.group_id, is_active=True).exclude(id=product.id).prefetch_related('variants__images')
        for sib in siblings:
            sib_vars = list(sib.variants.all())
            sib_first = sib_vars[0] if sib_vars else None
            sib_img = main_images[0]
            if sib_first and sib_first.images.first():
                sib_img = format_img_url(sib_first.images.first().image)
            color_variants.append({
                'id': str(sib.id),
                'name': sib.name,
                'slug': sib.slug,
                'color': sib.color_name or (sib_first.color if sib_first else ''),
                'colorHex': sib.color_hex or '#B8963E',
                'price': float(sib_first.discount_price or sib_first.price) if sib_first and sib_first.price else 0.0,
                'image': sib_img
            })

    return {
        '_id': str(product.id),
        'id': str(product.id),
        'name': product.name,
        'slug': product.slug,
        'price': first_price,
        'originalPrice': first_orig,
        'stock': stock,
        'tag': product.category.slug if product.category else 'suits',
        'groupId': getattr(product, 'group_id', ''),
        'colorName': getattr(product, 'color_name', '') or (first.color if first else ''),
        'colorHex': getattr(product, 'color_hex', '') or '#B8963E',
        'productType': getattr(product, 'product_type', 'readymade') or 'readymade',
        'product_type': getattr(product, 'product_type', 'readymade') or 'readymade',
        'isReadymade': (getattr(product, 'product_type', 'readymade') or 'readymade') == 'readymade',
        'colorVariants': color_variants,
        'variants': variant_data,
        'colors': colors,
        'image': main_images[0],
        'images': main_images,
        'description': product.description,
        'status': 'APPROVED' if product.is_active else 'HIDDEN',
        'category': {'id': str(product.category.id), 'name': product.category.name, 'slug': product.category.slug} if product.category else None,
        'seller': {
            'id': str(product.seller.id),
            'shopName': product.seller.business_name,
            'name': product.seller.user.get_full_name() or product.seller.user.username
        }
    }


class AuthRegisterView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        data = request.data
        email = data.get('email', '').lower().strip()
        if not email or not data.get('password') or not data.get('name'):
            return Response({'message': 'Name, email, and password are required'}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({'message': 'User with this email already exists'}, status=400)
        username = email.split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f'{username}_{User.objects.count()}'
        user = User.objects.create_user(username=username, email=email, password=data['password'],
                                        first_name=data['name'], phone_number=data.get('phone', ''))
        return Response({'token': token_for(user), 'user': user_data(user)}, status=201)


class AuthSellerRegisterView(AuthRegisterView):
    def post(self, request):
        response = super().post(request)
        if response.status_code != 201:
            return response
        user = User.objects.get(id=response.data['user']['id'])
        user.role = UserRole.SELLER
        user.save(update_fields=['role'])
        SellerProfile.objects.create(user=user, business_name=request.data.get('shopName', 'Vendor Atelier'),
            gst_number=f'DEMO{str(user.id).replace("-", "")[:11]}', pan=f'{str(user.id).replace("-", "")[:10]}',
            business_address=request.data.get('shopDescription', 'Online'), pickup_address='Online',
            contact_phone=request.data.get('phone', ''), contact_email=user.email,
            verification_status=VerificationStatus.APPROVED)
        response.data['user'] = user_data(user)
        return response


class AuthLoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        email, password = request.data.get('email'), request.data.get('password')
        user = User.objects.filter(email=email).first() if email else None
        user = authenticate(username=user.username, password=password) if user else None
        if not user:
            return Response({'message': 'Invalid email or password'}, status=400)
        return Response({'token': token_for(user), 'user': user_data(user)})


class AuthMeView(APIView):
    def get(self, request): return Response({'user': user_data(request.user)})


class AuthSendOtpView(APIView):
    permission_classes = (permissions.AllowAny,)
    def post(self, request):
        digits = ''.join(c for c in str(request.data.get('phone', '')) if c.isdigit())
        if len(digits) < 10: return Response({'message': 'Valid phone number is required (at least 10 digits)'}, status=400)
        return Response({'success': True, 'message': 'OTP sent successfully to your phone', 'devOtp': digits[-6:]})


class AuthVerifyOtpView(APIView):
    permission_classes = (permissions.AllowAny,)
    def post(self, request):
        phone, otp = str(request.data.get('phone', '')), str(request.data.get('otp', ''))
        digits = ''.join(c for c in phone if c.isdigit())
        if not phone or not otp: return Response({'message': 'Phone number and OTP are required'}, status=400)
        if otp != digits[-6:]: return Response({'message': 'Invalid OTP. Please try again.'}, status=401)
        user = User.objects.filter(phone_number__icontains=digits[-10:]).first()
        if not user:
            user = User.objects.create_user(username=f'{digits}@phone.riwaaya.com', email=f'{digits}@phone.riwaaya.com', password=f'phone_{digits}', phone_number=phone, first_name=f'User {digits[-4:]}')
        return Response({'token': token_for(user), 'user': user_data(user)})


def filter_and_paginate_products(request, qs):
    qs = qs.select_related('category', 'seller__user').prefetch_related('variants__inventory', 'variants__images')
    search = request.query_params.get('search') or request.query_params.get('query')
    tag = request.query_params.get('tag') or request.query_params.get('category')
    stock_status = request.query_params.get('stock') or request.query_params.get('stockStatus')
    status_param = request.query_params.get('status') or request.query_params.get('is_active')
    sort_by = request.query_params.get('sort') or request.query_params.get('sortBy') or 'newest'
    
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
        
    try:
        page_size = max(1, min(100, int(request.query_params.get('pageSize', request.query_params.get('limit', 10)))))
    except (ValueError, TypeError):
        page_size = 10

    if search:
        qs = qs.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search) | 
            Q(slug__icontains=search) | 
            Q(variants__sku__icontains=search)
        ).distinct()

    if tag and tag != 'all':
        if tag == 'suits':
            qs = qs.filter(Q(category__slug='suits') | Q(category__isnull=True))
        else:
            qs = qs.filter(Q(category__slug=tag) | Q(category__name__icontains=tag))

    if status_param and status_param != 'all':
        if status_param.lower() in ('active', 'approved', 'true'):
            qs = qs.filter(is_active=True)
        elif status_param.lower() in ('hidden', 'rejected', 'false', 'draft'):
            qs = qs.filter(is_active=False)

    if stock_status and stock_status != 'all':
        if stock_status == 'out_of_stock':
            qs = qs.filter(Q(variants__inventory__available_stock__lte=0) | Q(variants__inventory__isnull=True)).distinct()
        elif stock_status == 'low_stock':
            qs = qs.filter(variants__inventory__available_stock__gt=0, variants__inventory__available_stock__lte=5).distinct()
        elif stock_status == 'in_stock':
            qs = qs.filter(variants__inventory__available_stock__gt=0).distinct()

    if sort_by == 'price_asc':
        qs = qs.order_by('variants__price')
    elif sort_by == 'price_desc':
        qs = qs.order_by('-variants__price')
    elif sort_by == 'stock_asc':
        qs = qs.order_by('variants__inventory__available_stock')
    elif sort_by == 'stock_desc':
        qs = qs.order_by('-variants__inventory__available_stock')
    elif sort_by == 'name_asc':
        qs = qs.order_by('name')
    else:
        qs = qs.order_by('-created_at')

    total_count = qs.count()
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    start = (page - 1) * page_size
    end = start + page_size
    paginated_qs = list(qs[start:end])

    # Deduplicate by group_id so styles aren't duplicated across sub-products
    seen_group_ids = set()
    deduped_qs = []
    for p in paginated_qs:
        g_id = getattr(p, 'group_id', None)
        if g_id:
            if g_id in seen_group_ids:
                continue
            seen_group_ids.add(g_id)
        deduped_qs.append(p)

    data = []
    for p in deduped_qs:
        p_info = product_data(request, p)
        colors_list = p_info.get('colors') or []
        if len(colors_list) > 1:
            for col in colors_list:
                col_name = col['name']
                col_hex = col.get('colorHex') or col.get('hex') or '#B8963E'
                col_vars = [v for v in p_info.get('variants', []) if (v.get('color') or '').strip().lower() == col_name.strip().lower()]
                
                col_imgs = []
                for v in col_vars:
                    for img in v.get('images', []):
                        if img and img not in col_imgs:
                            col_imgs.append(img)
                if not col_imgs:
                    col_imgs = p_info.get('images', [])

                c_item = dict(p_info)
                c_item['cardId'] = f"{p_info['id']}_{slugify(col_name)}"
                c_item['colorName'] = col_name
                c_item['colorHex'] = col_hex
                c_item['image'] = col_imgs[0] if col_imgs else p_info['image']
                c_item['images'] = col_imgs if col_imgs else p_info['images']
                if col_vars:
                    v_p = col_vars[0].get('price', p_info['price'])
                    v_op = col_vars[0].get('originalPrice', p_info['originalPrice'])
                    c_item['price'] = v_p
                    c_item['originalPrice'] = v_op
                    c_item['stock'] = sum(v.get('stock', 0) for v in col_vars)
                data.append(c_item)
        else:
            data.append(p_info)

    return {
        'data': data,
        'pagination': {
            'total': len(data),
            'page': page,
            'totalPages': total_pages,
            'pageSize': page_size,
            'hasNext': page < total_pages,
            'hasPrev': page > 1
        }
    }


class ProductListCreateView(APIView):
    def get_permissions(self): return [permissions.AllowAny()] if self.request.method == 'GET' else [permissions.IsAuthenticated()]
    def get(self, request):
        seller = getattr(request.user, 'seller_profile', None) if request.user.is_authenticated else None
        if seller and request.user.role == UserRole.SELLER:
            qs = Product.objects.filter(seller=seller)
        else:
            qs = Product.objects.all()
        result = filter_and_paginate_products(request, qs)
        return node_response(
            result['data'], 
            'Products fetched successfully', 
            count=result['pagination']['total'], 
            pagination=result['pagination']
        )
    def post(self, request):
        if request.user.role not in (UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN):
            return Response({'message': 'Forbidden'}, status=403)
        seller = getattr(request.user, 'seller_profile', None) or SellerProfile.objects.first()
        if not seller:
            return Response({'message': 'Seller profile is required'}, status=400)
        name = request.data.get('name', 'New Atelier Suit')
        category_slug = request.data.get('tag', 'suits')
        category_names = {'suits': 'Pakistani Suits', 'coords': 'Co-Ord Sets', 'party': 'Party Wear', 'hampers': 'Gift Hampers'}
        category, _ = Category.objects.get_or_create(slug=category_slug, defaults={'name': category_names.get(category_slug, category_slug.title())})
        variants = request.data.get('variants') or [{}]
        
        product_image_sources = list(dict.fromkeys(
            [str(k) for k in request.data.get('imageKeys', []) if k] +
            [str(u) for u in request.data.get('images', []) if u]
        ))

        master_group_id = f"STYLE-{slugify(name)[:15].upper()}-{str(UUID(int=__import__('uuid').uuid4().int))[:6]}"
        first_hex = '#B8963E'
        first_color = ''
        if isinstance(variants, list) and len(variants) > 0 and isinstance(variants[0], dict):
            first_hex = variants[0].get('colorHex', '#B8963E')
            first_color = variants[0].get('color', '')

        with transaction.atomic():
            # 1. Create single master product
            main_product = Product.objects.create(
                seller=seller,
                category=category,
                name=name,
                slug=f"{slugify(name)}-{str(UUID(int=__import__('uuid').uuid4().int))[:8]}",
                description=request.data.get('description', 'Handcrafted luxury apparel.'),
                group_id=master_group_id,
                color_name=first_color,
                color_hex=first_hex,
                product_type=request.data.get('productType') or request.data.get('product_type') or 'readymade',
                is_active=request.data.get('status', 'APPROVED') != 'HIDDEN'
            )
            # Synchronize color variants into individual Product records sharing group_id
            sync_product_group_colors(main_product, variants, product_image_sources)

        return node_response(product_data(request, main_product), 'Product created successfully with all variants', 201)


class ProductDetailView(APIView):
    permission_classes = (permissions.AllowAny,)
    def get(self, request, product_id):
        product = Product.objects.get(id=product_id)
        return node_response(product_data(request, product), 'Product details fetched')
    def put(self, request, product_id):
        product = Product.objects.get(id=product_id)
        for field in ('name', 'description'):
            if field in request.data: setattr(product, field, request.data[field])
        if 'productType' in request.data or 'product_type' in request.data:
            product.product_type = request.data.get('productType') or request.data.get('product_type') or 'readymade'
        category_value = request.data.get('category') or request.data.get('tag')
        if category_value is not None:
            category_map = {'1': 'suits', '2': 'coords', '3': 'party', '4': 'hampers'}
            category_slug = category_map.get(str(category_value), str(category_value).lower())
            category_names = {'suits': 'Pakistani Suits', 'coords': 'Co-Ord Sets', 'party': 'Party Wear', 'hampers': 'Gift Hampers'}
            category, _ = Category.objects.get_or_create(slug=category_slug, defaults={'name': category_names.get(category_slug, category_slug.title())})
            product.category = category
        if 'status' in request.data: product.is_active = request.data['status'] != 'HIDDEN'

        if not product.group_id:
            product.group_id = f"STYLE-{slugify(product.name)[:15].upper()}-{str(UUID(int=__import__('uuid').uuid4().int))[:6]}"
        product.save()

        variants_input = request.data.get('variants')
        product_image_sources = list(dict.fromkeys(
            [str(k) for k in request.data.get('imageKeys', []) if k] +
            [str(u) for u in request.data.get('images', []) if u]
        ))

        with transaction.atomic():
            if isinstance(variants_input, list) and len(variants_input) > 0:
                sync_product_group_colors(product, variants_input, product_image_sources)
            else:
                first_variant = product.variants.first()
                if first_variant and ('price' in request.data or 'originalPrice' in request.data):
                    selling_price = Decimal(str(request.data.get('price', first_variant.discount_price or first_variant.price)))
                    regular_price = Decimal(str(request.data.get('originalPrice', first_variant.price)))
                    first_variant.price = regular_price
                    first_variant.discount_price = selling_price if selling_price < regular_price else None
                    first_variant.save(update_fields=['price', 'discount_price', 'updated_at'])
                if first_variant and 'stock' in request.data:
                    inventory, _ = Inventory.objects.get_or_create(variant=first_variant)
                    inventory.available_stock = max(0, int(request.data.get('stock') or 0))
                    inventory.save(update_fields=['available_stock'])

            # Remove any duplicate sub-products from earlier runs
            if product.group_id:
                Product.objects.filter(group_id=product.group_id).exclude(id=product.id).delete()

        return node_response(product_data(request, product), 'Product updated successfully')
    def delete(self, request, product_id): Product.objects.filter(id=product_id).delete(); return node_response(None, 'Product deleted successfully')


class ProductVariantView(APIView):
    def post(self, request, product_id):
        product = Product.objects.get(id=product_id)
        variants_input = request.data.get('variants')
        
        if isinstance(variants_input, list) and len(variants_input) > 0:
            created_list = []
            with transaction.atomic():
                for v_item in variants_input:
                    if not isinstance(v_item, dict):
                        continue
                    sku = v_item.get('sku') or f'SKU-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}'
                    if Variant.objects.filter(sku=sku).exists():
                        sku = f'{sku}-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}'
                    selling_price = Decimal(str(v_item.get('price', 0)))
                    regular_price = Decimal(str(v_item.get('originalPrice', selling_price) or selling_price))
                    variant = Variant.objects.create(
                        product=product,
                        sku=sku,
                        size=v_item.get('size', ''),
                        color=v_item.get('color', ''),
                        price=regular_price,
                        discount_price=selling_price if selling_price < regular_price else None
                    )
                    Inventory.objects.create(variant=variant, available_stock=int(v_item.get('stock', 0)))
                    for image_key in (v_item.get('imageKeys') or []):
                        if image_key:
                            ProductImage.objects.create(variant=variant, image=str(image_key))
                    created_list.append({'id': str(variant.id), 'sku': variant.sku, 'size': variant.size, 'color': variant.color})
            return node_response({'createdCount': len(created_list), 'variants': created_list}, 'Variants created successfully', 201)

        sku = request.data.get('sku') or f'SKU-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}'
        if Variant.objects.filter(sku=sku).exists():
            sku = f'{sku}-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}'
        price = Decimal(str(request.data.get('price', 0)))
        original_price = Decimal(str(request.data.get('originalPrice', price) or price))
        variant = Variant.objects.create(
            product=product,
            sku=sku,
            size=request.data.get('size', ''),
            color=request.data.get('color', ''),
            price=original_price,
            discount_price=price if price < original_price else None
        )
        Inventory.objects.create(variant=variant, available_stock=int(request.data.get('stock', 0)))
        for image_key in request.data.get('imageKeys', []):
            if image_key:
                ProductImage.objects.create(variant=variant, image=str(image_key))
        return node_response({'id': str(variant.id), 'sku': variant.sku, 'size': variant.size, 'color': variant.color}, 'Variant created successfully', 201)


class ProductUploadView(APIView):
    def post(self, request):
        files = request.FILES.getlist('images')
        if not files: return Response({'message': 'No image files uploaded'}, status=400)
        keys = []
        urls = []
        for uploaded_file in files:
            key = default_storage.save(f'product_images/{UUID(int=__import__("uuid").uuid4().int)}-{uploaded_file.name}', ContentFile(uploaded_file.read()))
            keys.append(key)
            url = default_storage.url(key)
            if not (url.startswith('http://') or url.startswith('https://')):
                url = request.build_absolute_uri(url)
            urls.append(url)
        return node_response({'urls': urls, 'keys': keys}, 'Images uploaded successfully')


class CartView(APIView):
    permission_classes = (permissions.AllowAny,)
    def _guest_session_id(self, request):
        return (
            request.headers.get('x-session-id')
            or request.query_params.get('sessionId')
            or request.data.get('sessionId')
            or 'default_guest_session'
        )
    def _key(self, request):
        if request.user.is_authenticated:
            return f'user:{request.user.id}'
        return f'session:{self._guest_session_id(request)}'
    def _cart(self, request):
        if not request.user.is_authenticated:
            return GuestCart.objects.filter(session_id=self._guest_session_id(request)).values_list('items', flat=True).first() or []
        return request.session.get(self._key(request), [])
    def _response(self, request, items, message='Cart details fetched'):
        if not request.user.is_authenticated:
            GuestCart.objects.update_or_create(session_id=self._guest_session_id(request), defaults={'items': items})
        else:
            request.session[self._key(request)] = items
        subtotal = sum(Decimal(str(i['price'])) * i['quantity'] for i in items); shipping = 0 if subtotal == 0 or subtotal >= 5000 else 350
        return node_response({'items': items, 'subtotal': float(subtotal), 'shipping': shipping, 'discount': 0, 'grandTotal': float(subtotal + shipping)}, message)
    def get(self, request): return self._response(request, self._cart(request))
    def post(self, request):
        raw_product_id = str(request.data.get('productId') or '').strip()
        clean_product_id = raw_product_id.split('_')[0]
        size = str(request.data.get('size') or 'M').strip()
        color = str(request.data.get('color') or '').strip()
        req_name = str(request.data.get('name') or '').strip()
        req_image = str(request.data.get('image') or '').strip()

        product = Product.objects.filter(id=clean_product_id).first()
        if not product:
            try:
                product = Product.objects.get(id=clean_product_id)
            except Exception:
                product = Product.objects.filter(Q(id=clean_product_id) | Q(slug=clean_product_id)).first()

        if not product:
            return Response({'message': 'Product not found'}, status=404)

        # Match variant by color/size
        variant = None
        if color:
            variant = product.variants.filter(color__iexact=color, size__iexact=size).first()
            if not variant:
                variant = product.variants.filter(color__iexact=color).first()
            if not variant:
                variant = product.variants.filter(color__icontains=color).first()
        if not variant:
            variant = product.variants.filter(size__iexact=size).first()
        if not variant:
            variant = product.variants.first()

        def resolve_img(img_val):
            if not img_val:
                return ""
            s = str(img_val).strip()
            if not s:
                return ""
            if s.startswith('http://') or s.startswith('https://'):
                return s
            if s.startswith('/assets/'):
                return s
            try:
                url = default_storage.url(s)
                if url.startswith('http://') or url.startswith('https://'):
                    return url
                return request.build_absolute_uri(url)
            except Exception:
                pass
            if '/media/' in s:
                clean_rel = s.split('/media/')[-1]
                return request.build_absolute_uri('/media/' + clean_rel)
            return request.build_absolute_uri('/media/' + s.lstrip('/'))

        image_url = ""
        # If frontend passed specific card/variant image, honor it
        if req_image:
            image_url = resolve_img(req_image)

        if not image_url and variant:
            v_img = variant.images.first()
            if v_img:
                image_url = resolve_img(v_img.image)

        if not image_url:
            for v in product.variants.all():
                v_img = v.images.first()
                if v_img:
                    image_url = resolve_img(v_img.image)
                    if image_url:
                        break

        if not image_url:
            image_url = "/assets/1540aab590cd7d478ad01cdb1a615d469ef2a808.png"

        item_price = float(variant.discount_price or variant.price) if variant and variant.price else float(request.data.get('price', 0))
        item_color = color if color else (variant.color if variant and variant.color else getattr(product, 'color_name', '') or 'Standard')
        item_name = req_name if req_name else product.name

        items = self._cart(request)
        item_key = f"{clean_product_id}_{slugify(item_color)}_{slugify(size)}"
        
        existing = next((i for i in items if (i.get('productId') == raw_product_id or i.get('productId') == clean_product_id) and str(i.get('size', '')).lower() == size.lower() and str(i.get('color', '')).lower() == item_color.lower()), None)

        item = {
            'id': f'cart_{item_key}',
            'productId': raw_product_id,
            'name': item_name,
            'category': product.category.slug if product.category else 'suits',
            'price': item_price,
            'image': image_url,
            'size': size,
            'color': item_color,
            'quantity': int(request.data.get('quantity', 1))
        }

        if existing:
            existing['quantity'] += item['quantity']
            existing['image'] = image_url
        else:
            items.append(item)

        return self._response(request, items, 'Item added to bag')
    def delete(self, request): return self._response(request, [], 'Cart cleared')


class CartItemView(CartView):
    def put(self, request, item_id):
        items = self._cart(request); quantity = int(request.data.get('quantity', 1)); items = [i for i in items if i['id'] != item_id or quantity > 0]
        for item in items:
            if item['id'] == item_id: item['quantity'] = quantity
        return self._response(request, items, 'Cart updated')
    def delete(self, request, item_id): return self.put(request, item_id) if request.data.get('quantity') else self._response(request, [i for i in self._cart(request) if i['id'] != item_id], 'Item removed from bag')


class CartMergeView(CartView):
    def post(self, request):
        guest_key = f'session:{request.data.get("sessionId", request.headers.get("x-session-id"))}'; items = self._cart(request); guest = request.session.get(guest_key, [])
        for incoming in guest:
            existing = next((i for i in items if i['productId'] == incoming['productId'] and i['size'] == incoming['size']), None)
            if existing: existing['quantity'] += incoming['quantity']
            else: items.append(incoming)
        request.session[guest_key] = []; return self._response(request, items, 'Guest cart merged into your account successfully')


class WishlistView(APIView):
    def get(self, request): return Response({'wishlist': request.session.get(f'wishlist:{request.user.id}', [])})


class WishlistToggleView(WishlistView):
    def post(self, request):
        key = f'wishlist:{request.user.id}'; ids = request.session.get(key, []); product_id = str(request.data.get('productId'))
        ids.remove(product_id) if product_id in ids else ids.append(product_id); request.session[key] = ids; return Response({'wishlist': ids})


class WishlistSyncView(WishlistView):
    def post(self, request):
        key = f'wishlist:{request.user.id}'; ids = list(dict.fromkeys(request.session.get(key, []) + [str(i) for i in request.data.get('wishlistIds', [])])); request.session[key] = ids; return Response({'wishlist': ids})


class AddressListView(APIView):
    def get(self, request): return Response([{'_id': str(a.id), 'id': str(a.id), 'title': 'Saved Address', 'name': a.recipient_name, 'phone': a.phone_number, 'street': a.street_address, 'city': a.city, 'state': a.state, 'pincode': a.postal_code, 'isDefault': a.is_default} for a in request.user.addresses.all()])
    def post(self, request):
        data = request.data
        required = ('name', 'phone', 'street', 'city', 'state', 'pincode')
        if any(not data.get(k) for k in required): return Response({'message': 'All address fields (name, phone, street, city, state, pincode) are required'}, status=400)
        if data.get('isDefault'): request.user.addresses.update(is_default=False)
        address = Address.objects.create(user=request.user, recipient_name=data['name'], phone_number=data['phone'], street_address=data['street'], city=data['city'], state=data['state'], postal_code=data['pincode'], country=data.get('country', 'Pakistan'), is_default=data.get('isDefault', not request.user.addresses.exists()))
        return Response(self.get(request).data, status=201)


class AddressDetailView(AddressListView):
    def put(self, request, address_id):
        address = Address.objects.get(id=address_id, user=request.user)
        if request.data.get('isDefault'): request.user.addresses.update(is_default=False)
        mapping = {'name': 'recipient_name', 'phone': 'phone_number', 'street': 'street_address', 'pincode': 'postal_code'}
        for source, target in mapping.items():
            if source in request.data: setattr(address, target, request.data[source])
        for field in ('city', 'state', 'is_default'):
            if field in request.data: setattr(address, field, request.data[field] if field != 'is_default' else request.data[field])
        address.save(); return Response(self.get(request).data)
    def delete(self, request, address_id): Address.objects.filter(id=address_id, user=request.user).delete(); return Response(self.get(request).data)


class OrderListCreateView(APIView):
    def get(self, request): return Response(list(Order.objects.filter(customer=request.user).values()))
    def post(self, request):
        items = request.data.get('orderItems', [])
        if not items: return Response({'message': 'No order items provided'}, status=400)
        total = Decimal('0'); order_items = []
        for item in items:
            variant = Variant.objects.filter(product_id=item.get('productId')).first() or Variant.objects.filter(id=item.get('variantId')).first()
            if not variant: continue
            price = variant.discount_price or variant.price; quantity = int(item.get('quantity', 1)); total += price * quantity
            order_items.append((variant, price, quantity, item))
        if not order_items: return Response({'message': 'No valid order items provided'}, status=400)
        address = request.data.get('shippingAddress', {}); order = Order.objects.create(customer=request.user, shipping_address=address, billing_address=address, subtotal=total, total_amount=total)
        for variant, price, quantity, item in order_items: OrderItem.objects.create(order=order, variant=variant, product_name=variant.product.name, sku=variant.sku, variant_details={'size': item.get('size'), 'color': item.get('color')}, price=price, quantity=quantity)
        request.session[f'user:{request.user.id}'] = []; return Response({'_id': str(order.id), 'id': str(order.id), 'totalAmount': float(total), 'status': 'PENDING', 'orderItems': items, 'shippingAddress': address}, status=201)


class OrderDetailView(APIView):
    def get(self, request, order_id):
        order = Order.objects.get(id=order_id, customer=request.user); return Response({'_id': str(order.id), 'id': str(order.id), 'status': order.status, 'totalAmount': float(order.total_amount), 'shippingAddress': order.shipping_address, 'orderItems': list(order.items.values())})


class SellerStatsView(APIView):
    def get(self, request):
        products = Product.objects.filter(seller__user=request.user); return Response({'revenue': float(sum((v.price for p in products for v in p.variants.all()), Decimal('0'))), 'ordersCount': Order.objects.count(), 'productsCount': products.count(), 'totalStock': sum(i.available_stock for p in products for v in p.variants.all() for i in [getattr(v, 'inventory', None)] if i)})


class SellerProductsView(APIView):
    def get(self, request):
        seller = getattr(request.user, 'seller_profile', None) or SellerProfile.objects.first()
        qs = Product.objects.filter(seller=seller) if seller else Product.objects.all()
        result = filter_and_paginate_products(request, qs)
        return node_response(
            result['data'],
            'Seller products fetched successfully',
            count=result['pagination']['total'],
            pagination=result['pagination']
        )


class SellerProductDetailView(ProductDetailView):
    pass


class SellerOrdersView(APIView):
    def get(self, request): return Response(list(Order.objects.order_by('-created_at').values()))


class SellerOrderStatusView(APIView):
    def put(self, request, order_id):
        order = Order.objects.get(id=order_id)
        new_status = request.data.get('status')
        if not new_status: return Response({'message': 'Status is required'}, status=400)
        allowed = {choice[0] for choice in OrderStatus.choices}
        order.status = new_status if new_status in allowed else OrderStatus.PENDING
        order.save(update_fields=['status', 'updated_at'])
        return Response({'message': 'Order status updated successfully', 'orderId': str(order.id), 'status': order.status})


class AdminStatsView(APIView):
    def get(self, request): return node_response({'totalPlatformRevenue': float(Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0), 'totalSellers': User.objects.filter(role=UserRole.SELLER).count(), 'pendingSellers': SellerProfile.objects.filter(verification_status=VerificationStatus.PENDING).count(), 'totalProducts': Product.objects.count(), 'pendingProducts': Product.objects.filter(is_active=False).count(), 'totalOrders': Order.objects.count()}, 'Admin metrics retrieved successfully')


class AdminSellersView(APIView):
    def get(self, request): return node_response([user_data(p.user) for p in SellerProfile.objects.select_related('user')], 'Sellers fetched successfully')


class AdminSellerApprovalView(APIView):
    def put(self, request, seller_id):
        profile = SellerProfile.objects.filter(id=seller_id).first() or SellerProfile.objects.get(user_id=seller_id)
        profile.verification_status = VerificationStatus.APPROVED if request.data.get('isApproved') else VerificationStatus.PENDING; profile.save(); return node_response(user_data(profile.user), 'Seller status updated')


class AdminProductApprovalView(APIView):
    def put(self, request, product_id):
        product = Product.objects.get(id=product_id); product.is_active = request.data.get('status', 'APPROVED') != 'HIDDEN'; product.save(); return node_response({'_id': str(product.id), 'status': 'APPROVED' if product.is_active else 'HIDDEN'}, 'Product status updated successfully')


class AdminOrdersView(APIView):
    def get(self, request): return node_response(list(Order.objects.order_by('-created_at').values()), 'Orders fetched successfully')


class AdminSeedView(APIView):
    def post(self, request): return node_response(None, 'Seeding completed successfully')


class PaymentCreateOrderView(APIView):
    def post(self, request):
        amount = request.data.get('amount')
        if not amount: return Response({'message': 'Amount is required'}, status=400)
        amount_minor = round(float(amount) * 100)
        order_id = f'order_dummy_{request.user.id}'
        return Response({'success': True, 'orderId': order_id, 'amount': amount_minor,
                         'currency': request.data.get('currency', 'INR'),
                         'keyId': os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_dummy_key'),
                         'isDummy': True})


class PaymentVerifyView(APIView):
    def post(self, request):
        order_id = request.data.get('razorpay_order_id')
        payment_id = request.data.get('razorpay_payment_id')
        signature = request.data.get('razorpay_signature')
        if not order_id or not payment_id or not signature:
            return Response({'message': 'Missing Razorpay verification details'}, status=400)
        if order_id.startswith('order_dummy_'):
            return Response({'success': True, 'message': 'Dummy payment verified successfully'})
        secret = os.environ.get('RAZORPAY_KEY_SECRET', 'rzp_test_dummy_secret')
        expected = hmac.new(secret.encode(), f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return Response({'success': False, 'message': 'Invalid payment signature'}, status=400)
        return Response({'success': True, 'message': 'Payment verified successfully'})


class HealthView(APIView):
    permission_classes = (permissions.AllowAny,)
    def get(self, request): return Response({'status': 'OK', 'service': 'Riwaaya Django REST API'})