from decimal import Decimal


def unit_price(product, variant=None) -> Decimal:
    """Price of one unit: the variant override when set, else the product price."""
    if variant is not None and variant.price_override is not None:
        return Decimal(variant.price_override)
    return Decimal(product.effective_price)


def available_stock(product, variant=None) -> int:
    """Units that can be ordered for this product/variant."""
    return variant.stock if variant is not None else product.stock
