from decimal import Decimal


def unit_price(product, variant=None) -> Decimal:
    """Price of one unit: the variant override when set, else the product price."""
    if variant is not None and variant.price_override is not None:
        return Decimal(variant.price_override)
    return Decimal(product.effective_price)


def available_stock(product, variant=None) -> int:
    """Units that can be ordered for this product/variant."""
    return variant.stock if variant is not None else product.stock


def cart_line_image(product, variant=None):
    """Image URL for a cart/order line.

    Preference: the variant's own image, then the product's primary image, its
    first image, and finally its og_image. Returns None when there is none.
    """
    if variant is not None and variant.image:
        return variant.image.url
    images = product.images
    chosen = images.filter(is_primary=True).first() or images.first()
    if chosen:
        return chosen.image.url
    if product.og_image:
        return product.og_image.url
    return None
