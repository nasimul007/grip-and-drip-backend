from decimal import Decimal
from django.utils.html import escape
from apps.products.models import Product

DRY_RUN = False  # True: only list what would change

START = "<h2>Why Choose Gadget &amp; Widget"
END = "<p>Shop with confidence at Gadget &amp; Widget!</p>"

TEMPLATE = """<h2>Why Choose Gadget &amp; Widget – Your Trusted Gadget Shop in Bangladesh</h2>
<p>Welcome to <strong>Gadget &amp; Widget</strong>, your online destination for quality gadgets and tech accessories at competitive prices. From chargers and power banks to wireless earbuds, smartwatches, and more, we bring you carefully selected products for your everyday needs.</p>
<p>We focus on product quality, fair pricing, transparent information, and customer satisfaction. Enjoy convenient online shopping, helpful customer support, and reliable delivery right to your doorstep.</p>
<p><strong>Gadget &amp; Widget – Quality Gadgets. Honest Service. Great Value.</strong></p>
<h2>What Is the Price of {name} in Bangladesh?</h2>
<p>Looking for the latest price of {name} in Bangladesh? At Gadget &amp; Widget, we strive to offer quality gadgets and accessories at competitive prices.</p>
<p>{price_sentence} You can conveniently place your order through our website and get your favorite gadget delivered to your doorstep.</p>
<p>We aim to keep our product prices and availability information up to date so you can make an informed purchasing decision.</p>
<p>Shop with confidence at Gadget &amp; Widget!</p>"""


def taka(amount):
    amount = Decimal(amount)
    return f"৳{amount:,.0f}" if amount == amount.to_integral_value() else f"৳{amount:,.2f}"


def price_sentence(product, name):
    variants = list(product.variants.filter(is_active=True))
    prices = {Decimal(v.price_override) if v.price_override is not None else Decimal(product.price) for v in variants}
    prices = prices or {Decimal(product.price)}
    if len(prices) > 1:
        return f"The price of {name} starts from {taka(min(prices))}, depending on the option you choose."
    return f"The current price of {name} is {taka(min(prices))}."


def with_block(description, block):
    description = description or ""
    start = description.find(START)
    if start != -1:
        end = description.find(END, start)
        if end != -1:
            return description[:start] + block + description[end + len(END):]
    return description + ("\n" if description else "") + block


added = refreshed = same = 0
for p in Product.objects.filter(soft_deleted=False).order_by("id"):
    name = escape(p.name)
    new = with_block(p.description, TEMPLATE.format(name=name, price_sentence=price_sentence(p, name)))
    if new == (p.description or ""):
        same += 1
        continue
    had_it = START in (p.description or "")
    if not DRY_RUN:
        p.description = new
        p.save()
    refreshed += had_it
    added += not had_it
    print(("Refreshed" if had_it else "Added") + f": #{p.pk} {p.name}")

print(f"{'DRY RUN, nothing saved. ' if DRY_RUN else ''}Added {added}, refreshed {refreshed}, already up to date {same}.")