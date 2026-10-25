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

    Preference: the selected variant's image, then the product's display image
    (primary, first, or an active variant image), then its og_image. Returns
    None when there is none.
    """
    if variant is not None and variant.image:
        return variant.image.url
    found = product.display_image()
    if found:
        return found[0].url
    if product.og_image:
        return product.og_image.url
    return None
