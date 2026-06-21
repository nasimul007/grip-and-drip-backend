# Session Summary — Grip & Drip Backend + Frontend Integration

## Date: June 22, 2026

---

## What Has Been Done

### JWT Authentication (Backend)

**Packages installed:**
- `djangorestframework-simplejwt==5.5.1`
- `django-cors-headers==4.9.0`
- `pyjwt==2.13.0`

**Files modified:**
| File | Change |
|---|---|
| `pyproject.toml` | Added both packages to dependencies |
| `config/settings/base.py` | Added `rest_framework_simplejwt`, `corsheaders` to INSTALLED_APPS; corsheaders middleware; JWT auth classes; SIMPLE_JWT config; CORS_ALLOWED_ORIGINS |
| `config/urls.py` | Added `path("api/auth/", include("apps.accounts.urls"))` |

**Files created:**
| File | Purpose |
|---|---|
| `apps/accounts/serializers.py` | `RegisterSerializer` + `UserSerializer` |
| `apps/accounts/views.py` | `RegisterView` + `UserProfileView` |
| `apps/accounts/urls.py` | 4 auth routes |

**Available Auth Endpoints:**
| Method | Endpoint | Auth | Returns |
|---|---|---|---|
| POST | `/api/auth/register/` | Public | `{user, access, refresh}` |
| POST | `/api/auth/login/` | Public | `{access, refresh}` |
| POST | `/api/auth/token/refresh/` | Public | `{access}` |
| GET | `/api/auth/profile/` | JWT | `{id, username, email, phone_number, is_vendor}` |
| PUT/PATCH | `/api/auth/profile/` | JWT | Updated user object |

### Phase A: Cart, Order & Checkout (Backend)

**New app created:** `apps/orders/`

**Models:**
| Model | Purpose |
|---|---|
| `ShippingRate` | Dynamic shipping costs (inside/outside Dhaka, free threshold) |
| `Cart` | OneToOne to user, persists across sessions |
| `CartItem` | Product + optional variant + quantity |
| `Order` | Full order with auto-generated number (`ORD-YYYYMMDD-XXXX`) |
| `OrderItem` | Snapshots of product data at time of purchase |
| `ShippingAddress` | Address linked to each order |

**Files created:**
| File | Purpose |
|---|---|
| `apps/orders/__init__.py` | App package |
| `apps/orders/models.py` | 6 models (ShippingRate, Cart, CartItem, Order, OrderItem, ShippingAddress) |
| `apps/orders/serializers.py` | Serializers for all models + input validation |
| `apps/orders/views.py` | 9 views (Cart CRUD, Shipping rates, Order CRUD) |
| `apps/orders/urls.py` | 9 routes |
| `apps/orders/admin.py` | Full admin registration with inlines |

**Files modified:**
| File | Change |
|---|---|
| `config/settings/base.py` | Added `"apps.orders"` to INSTALLED_APPS |
| `config/urls.py` | Added `path("api/", include("apps.orders.urls"))` |

**Available Order Endpoints:**
| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/api/cart/` | JWT | Get user's cart with items |
| POST | `/api/cart/add/` | JWT | Add product (+ variant) to cart |
| PATCH | `/api/cart/items/<id>/` | JWT | Update item quantity |
| DELETE | `/api/cart/items/<id>/` | JWT | Remove item from cart |
| DELETE | `/api/cart/items/<id>/remove/` | JWT | Remove item (alt) |
| POST | `/api/cart/clear/` | JWT | Clear all items |
| GET | `/api/shipping-rates/` | Public | List active shipping rates |
| POST | `/api/orders/` | JWT | Place order (cart → order, clears cart) |
| GET | `/api/orders/list/` | JWT | List user's orders |
| GET | `/api/orders/<id>/` | JWT | Order detail with items + address |

**Key decisions:**
- **Shipping:** Dynamic rates via `ShippingRate` model with `free_shipping_minimum` threshold
- **Order number:** Format `ORD-YYYYMMDD-XXXX` (auto-incrementing daily sequence)
- **Cart:** Persists on backend for authenticated users; unauthenticated cart handled via frontend localStorage
- **Order creation flow:** Frontend sends `{shipping_rate_id, shipping_address, notes}` → backend calculates subtotal/shipping/total → creates Order + OrderItem snapshots + ShippingAddress → clears cart

---

### Frontend Template (Not Yet Integrated)
- Located at: `/home/nasimul/Downloads/grip-and-drip-nextjs-frontend`
- Next.js 16, React 19, Tailwind CSS 3, Redux Toolkit, Sanity CMS, NextAuth
- 17 pages, all hardcoded data, zero API calls
- Redux slices: cart, wishlist, productDetails, quickView

---

## Remaining Backend Roadmap

### Phase B: Contact & Newsletter
- **New app:** `apps/contact/`
- **Models:** ContactMessage, NewsletterSubscriber
- **Endpoints:** POST `/api/contact/`, `/api/newsletter/subscribe/`, `/api/newsletter/unsubscribe/`

### Phase C: Blog
- **New app:** `apps/blog/`
- **Models:** BlogCategory, BlogPost, BlogTag
- **Endpoints:** GET `/api/blog/`, `/api/blog/<slug>/`, `/api/blog/categories/`

### Phase D: Reviews/Ratings (Optional)
- Product review model + endpoints

---

## Frontend Integration (After Backend is Complete)

- Create `src/lib/api.ts` — API client with JWT handling
- Set up `.env.local` with `NEXT_PUBLIC_API_URL`
- Replace hardcoded data with API calls across all 17 pages
- Wire auth forms to `/api/auth/` endpoints
- Wire cart to Redux + API sync
- Wire checkout to order placement
- Dynamic routing for product details (`shop/[slug]`)
- Wire contact form, newsletter, blog

---

## Key Decisions

- **Package manager:** `uv` for Python, `npm` for Next.js
- **Auth:** JWT via SimpleJWT, Bearer tokens, access=1 day / refresh=7 days
- **CORS:** Allow `http://localhost:3000` (Next.js dev server)
- **Default permissions:** All public (AllowAny) — only cart/orders/profile require JWT
- **Cart strategy:** Client-side Redux + backend API sync (decided not yet finalized)
- **Register returns tokens:** Yes (user doesn't need separate login after signup)

---

## Environment

- **Backend:** `/home/nasimul/Documents/personal project/grip-and-drip-backend/`
- **Frontend:** `/home/nasimul/Downloads/grip-and-drip-nextjs-frontend/`
- **Python:** 3.12, Django 5.2, DRF 3.17+
- **Node:** Next.js 16, React 19

---

## Next Steps

### Phase B: Contact & Newsletter

- **New app:** `apps/contact/`
- **Models:**
  - `ContactMessage` — name, email, subject, message, is_read, created_at
  - `NewsletterSubscriber` — email (unique), is_active, subscribed_at
- **Endpoints:**
  - POST `/api/contact/` — Public, submit contact form
  - POST `/api/newsletter/subscribe/` — Public, subscribe email
  - POST `/api/newsletter/unsubscribe/` — Public, unsubscribe
- **Files to create:** `apps/contact/__init__.py`, `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`
- **Files to modify:** `config/settings/base.py`, `config/urls.py`

### Phase C: Blog
- **New app:** `apps/blog/`
- **Models:** BlogCategory, BlogPost, BlogTag
- **Endpoints:** GET `/api/blog/`, `/api/blog/<slug>/`, `/api/blog/categories/`

### Phase D: Reviews/Ratings (Optional)
- Product review model + endpoints

### Phase E: Frontend Integration
- Wire all 17 pages to backend APIs
