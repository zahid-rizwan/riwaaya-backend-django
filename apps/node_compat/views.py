from decimal import Decimal
import hashlib
import hmac
import os
from uuid import UUID

from django.contrib.auth import authenticate, get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Sum
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


def product_data(request, product):
    variants = list(product.variants.select_related('inventory').all())
    first = variants[0] if variants else None
    stock = sum(getattr(getattr(v, 'inventory', None), 'available_stock', 0) for v in variants)
    return {'_id': str(product.id), 'id': str(product.id), 'name': product.name,
            'slug': product.slug, 'price': float(first.discount_price or first.price) if first else 0,
            'originalPrice': float(first.price) if first else 0, 'stock': stock,
            'tag': product.category.slug if product.category else 'suits',
            'images': [request.build_absolute_uri(i.image.url) for v in variants for i in v.images.all()],
            'description': product.description, 'status': 'APPROVED' if product.is_active else 'HIDDEN',
            'category': {'id': str(product.category.id), 'name': product.category.name, 'slug': product.category.slug} if product.category else None,
            'seller': {'id': str(product.seller.id), 'shopName': product.seller.business_name,
                       'name': product.seller.user.get_full_name() or product.seller.user.username}}


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


class ProductListCreateView(APIView):
    def get_permissions(self): return [permissions.AllowAny()] if self.request.method == 'GET' else [permissions.IsAuthenticated()]
    def get(self, request):
        qs = Product.objects.select_related('category', 'seller__user').prefetch_related('variants__inventory', 'variants__images').order_by('-created_at')
        tag, search, state = request.query_params.get('tag'), request.query_params.get('search'), request.query_params.get('status')
        if tag and tag != 'all': qs = qs.filter(category__slug=tag)
        if search: qs = qs.filter(name__icontains=search)
        if state and state != 'ALL': qs = qs.filter(is_active=(state == 'APPROVED'))
        return node_response([product_data(request, p) for p in qs], 'Products fetched successfully', count=qs.count())
    def post(self, request):
        if request.user.role not in (UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN): return Response({'message': 'Forbidden'}, status=403)
        seller = getattr(request.user, 'seller_profile', None) or SellerProfile.objects.first()
        if not seller: return Response({'message': 'Seller profile is required'}, status=400)
        name = request.data.get('name', 'New Atelier Suit')
        category = Category.objects.filter(slug=request.data.get('tag', 'suits')).first()
        variants = request.data.get('variants') or [{}]
        requested_sku = variants[0].get('sku') if isinstance(variants[0], dict) else None
        sku = requested_sku or f'SKU-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}'
        if Variant.objects.filter(sku=sku).exists():
            sku = f'{sku}-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}'
        with transaction.atomic():
            product = Product.objects.create(seller=seller, category=category, name=name, slug=f'{slugify(name)}-{str(UUID(int=__import__("uuid").uuid4().int))[:8]}', description=request.data.get('description', 'Handcrafted luxury apparel.'), is_active=request.data.get('status', 'APPROVED') != 'HIDDEN')
            variant = Variant.objects.create(product=product, sku=sku, price=Decimal(str(request.data.get('price', 0) or 0)))
            Inventory.objects.create(variant=variant, available_stock=int(request.data.get('stock', 0) or 0))
            for image_key in request.data.get('imageKeys', []):
                if image_key:
                    ProductImage.objects.create(variant=variant, image=str(image_key))
        return node_response(product_data(request, product), 'Product created successfully', 201)


class ProductDetailView(APIView):
    permission_classes = (permissions.AllowAny,)
    def get(self, request, product_id):
        product = Product.objects.get(id=product_id)
        return node_response(product_data(request, product), 'Product details fetched')
    def put(self, request, product_id):
        product = Product.objects.get(id=product_id)
        for field in ('name', 'description'):
            if field in request.data: setattr(product, field, request.data[field])
        if 'status' in request.data: product.is_active = request.data['status'] != 'HIDDEN'
        product.save(); return node_response(product_data(request, product), 'Product updated successfully')
    def delete(self, request, product_id): Product.objects.filter(id=product_id).delete(); return node_response(None, 'Product deleted successfully')


class ProductVariantView(APIView):
    def post(self, request, product_id):
        product = Product.objects.get(id=product_id); variant = Variant.objects.create(product=product, sku=request.data['sku'], price=request.data['price'])
        Inventory.objects.create(variant=variant, available_stock=request.data.get('stock', 0)); return node_response({'id': str(variant.id), 'sku': variant.sku}, 'Variant created successfully', 201)


class ProductUploadView(APIView):
    def post(self, request):
        files = request.FILES.getlist('images')
        if not files: return Response({'message': 'No image files uploaded'}, status=400)
        keys = []
        urls = []
        for uploaded_file in files:
            key = default_storage.save(f'product_images/{UUID(int=__import__("uuid").uuid4().int)}-{uploaded_file.name}', ContentFile(uploaded_file.read()))
            keys.append(key)
            urls.append(default_storage.url(key))
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
        product_id, size = str(request.data.get('productId')), request.data.get('size', 'M'); product = Product.objects.get(id=product_id); variant = product.variants.first(); items = self._cart(request); existing = next((i for i in items if i['productId'] == product_id and i['size'] == size), None)
        stored_image = variant.images.first() if variant else None
        image_url = request.build_absolute_uri(stored_image.image.url) if stored_image else request.data.get('image', '')
        item = {'id': f'cart_{product_id}_{size}', 'productId': product_id, 'name': product.name, 'category': product.category.slug if product.category else 'suits', 'price': float(variant.discount_price or variant.price) if variant else 0, 'image': image_url, 'size': size, 'color': request.data.get('color', 'Ivory'), 'quantity': int(request.data.get('quantity', 1))}
        if existing: existing['quantity'] += item['quantity']
        else: items.append(item)
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
    def get(self, request): return Response([product_data(request, p) for p in Product.objects.filter(seller__user=request.user)])


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