import os
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.products.models import Product, ProductImage, ProductVariant


def guess_ext(url):
    url = url.split("?")[0].split("#")[0]
    if url.endswith(".png") or "png-alpha" in url or "png" in url.lower():
        return ".png"
    if url.endswith(".webp"):
        return ".webp"
    return ".jpg"


def download_image(product, url, index, images_dir, product_name=None):
    base_slug = product.slug
    ext = guess_ext(url)
    filename = f"{index}{ext}"
    filepath = images_dir / filename

    try:
        urllib.request.urlretrieve(url, filepath)
        size = filepath.stat().st_size
        if size < 1000:
            filepath.unlink()
            return None
        img = ProductImage.objects.create(
            product=product,
            image=f"products/images/{base_slug}/{filename}",
            alt_text=f"{product_name or product.name} - View {index+1}",
            is_primary=(index == 0),
            sort_order=index,
        )
        return filename, filepath
    except Exception:
        if filepath.exists():
            filepath.unlink()
        return None


def populate_product(pid, image_urls, desc_html="", meta_title="", meta_desc=""):
    try:
        product = Product.objects.get(id=pid)
    except Product.DoesNotExist:
        print(f"  SKIP: Product ID {pid} not found")
        return

    print(f"\n{'='*60}")
    print(f"Product ID {pid}: {product.name}")

    base_slug = product.slug
    images_subdir = Path(settings.MEDIA_ROOT) / "products" / "images" / base_slug
    og_subdir = Path(settings.MEDIA_ROOT) / "products" / "og" / base_slug
    images_subdir.mkdir(parents=True, exist_ok=True)
    og_subdir.mkdir(parents=True, exist_ok=True)

    product.images.all().delete()

    downloaded = []
    for i, url in enumerate(image_urls):
        if not url:
            continue
        result = download_image(product, url.strip(), i, images_subdir)
        if result:
            downloaded.append(result)
            print(f"  OK: image {i+1}/{len(image_urls)}")
        else:
            print(f"  FAIL: image {i+1}/{len(image_urls)}")

    if downloaded:
        primary_filename, primary_path = downloaded[0]
        ext = Path(primary_filename).suffix or ".jpg"
        og_path = og_subdir / f"og{ext}"
        og_rel = f"products/og/{base_slug}/og{ext}"
        try:
            import shutil
            shutil.copy2(primary_path, og_path)
            product.og_image = og_rel
        except Exception as e:
            print(f"  og_image copy failed: {e}")

    if desc_html:
        product.description = desc_html

    product.meta_title = meta_title or f"{product.name} | Gadget & Widget"
    if meta_desc:
        product.meta_description = meta_desc

    product.save()

    variant = product.variants.filter(is_active=True).first()
    if variant and downloaded:
        variant.image = f"products/images/{base_slug}/{downloaded[0][0]}"
        variant.save()

    print(f"  Images: {len(downloaded)}/{len(image_urls)}")
    print(f"  meta_title: {product.meta_title}")
    print(f"  meta_description: {product.meta_description[:60] if product.meta_description else 'N/A'}...")
    print(f"  DONE")


class Command(BaseCommand):
    help = "Populate all remaining products with images and SEO"

    def handle(self, *args, **options):
        populate_product(19, [
            "https://images.samsung.com/is/image/samsung/p6pim/uk/ep-ta800xweggb/gallery/uk-wall-charger-super-fast-charging-25w-356757-ep-ta800xweggb-363992403?$650_519_PNG$",
            "https://i.ebayimg.com/images/g/zKEAAOSwg3BluR8M/s-l1600.webp",
            "https://i.ebayimg.com/images/g/Xb4AAOSwqY9jNWxX/s-l1600.webp",
        ],
        desc_html="""<p>Charge your Samsung devices at lightning speed with the Samsung 25W PD Adapter (UK Plug). This compact and powerful charger supports Samsung Super Fast Charging, delivering up to 25W of power for compatible Galaxy smartphones and tablets.</p>
<ul>
<li>Super Fast Charging up to 25W</li>
<li>PD 3.0 PPS support for optimized charging</li>
<li>UK 3-pin plug design</li>
<li>USB-C output interface</li>
<li>Compact and travel-friendly design</li>
</ul>""",
        meta_title="Samsung 25W PD Super Fast Charger UK Plug | Gadget & Widget",
        meta_desc="Buy Samsung 25W PD Adapter UK Plug. Super Fast Charging up to 25W with PD 3.0 PPS support. USB-C output, compact design. Fast shipping in Bangladesh.")

        populate_product(20, [
            "https://images.samsung.com/is/image/samsung/p6pim/uk/ep-t2510nbeggb/gallery/uk-25w-power-adapter-ep-t2510-481727-ep-t2510nbeggb-thumb-546028122",
            "https://i.ebayimg.com/images/g/zKEAAOSwg3BluR8M/s-l1600.webp",
        ],
        desc_html="""<p>Samsung 25W PD Adapter with EU plug design. Features Super Fast Charging technology with PD 3.0 PPS support for compatible Samsung Galaxy devices. Compact and travel-friendly.</p>
<ul>
<li>Super Fast Charging up to 25W</li>
<li>PD 3.0 PPS support</li>
<li>EU 2-pin round plug</li>
<li>USB-C output</li>
</ul>""",
        meta_title="Samsung 25W PD Adapter EU Plug | Gadget & Widget",
        meta_desc="Samsung 25W PD Adapter EU Plug with Super Fast Charging. PD 3.0 PPS, USB-C output, compact travel design. Order online in Bangladesh.")

        populate_product(21, [
            "https://images.samsung.com/is/image/samsung/p6pim/uk/ep-t4510xbeggb/gallery/uk-45w-travel-adapter-ep-t4510xbeggb-539014940?$650_519_PNG$",
            "https://images.samsung.com/is/image/samsung/p6pim/hk_en/ep-t4510xbeggb/gallery/hk-en-45w-power-adapter-ep-t4510-ep-t4510xbeggb-532014377?$650_519_PNG$",
            "https://images.samsung.com/is/image/samsung/p6pim/hk_en/ep-t4510xbeggb/gallery/hk-en-45w-power-adapter-ep-t4510-ep-t4510xbeggb-532014378?$650_519_PNG$",
            "https://images.samsung.com/is/image/samsung/p6pim/hk_en/ep-t4510xbeggb/gallery/hk-en-45w-power-adapter-ep-t4510-ep-t4510xbeggb-532014379?$650_519_PNG$",
            "https://i.ebayimg.com/images/g/zKEAAOSwg3BluR8M/s-l1600.webp",
        ],
        desc_html="""<p>Supercharge your Samsung Galaxy devices with the Samsung 45W PD Adapter (UK Plug). Experience Samsung Super Fast Charging 2.0 technology that powers your device from 0 to 65% in just 30 minutes.</p>
<ul>
<li>Super Fast Charging 2.0 up to 45W</li>
<li>PD 3.0 PDO / PPS up to 45W</li>
<li>UK 3-pin plug</li>
<li>USB-C output interface</li>
<li>Compatible with Galaxy S24+, S23+, S22+, Note10+, and more</li>
<li>Includes 1.8m USB-C to USB-C 5A cable</li>
</ul>""",
        meta_title="Samsung 45W PD Super Fast Charger 2.0 UK Plug | Gadget & Widget",
        meta_desc="Buy Samsung 45W PD Adapter UK Plug. Super Fast Charging 2.0 up to 45W with PD 3.0 PPS. Includes 1.8m USB-C cable. Fast delivery in Bangladesh.")

        populate_product(22, [
            "https://images.samsung.com/is/image/samsung/p6pim/au/eo-ic100bbegww/gallery/au-samsung-type-c-earphones-eo-ic100-eo-ic100bbegww-530300947?$650_519_PNG$",
            "https://images.samsung.com/is/image/samsung/p6pim/au/eo-ic100bbegww/gallery/au-samsung-type-c-earphones-eo-ic100-eo-ic100bbegww-530300948?$650_519_PNG$",
            "https://images.samsung.com/is/image/samsung/p6pim/au/eo-ic100bbegww/gallery/au-samsung-type-c-earphones-eo-ic100-eo-ic100bbegww-530300949?$650_519_PNG$",
            "https://images.samsung.com/is/image/samsung/p6pim/au/eo-ic100bbegww/gallery/au-samsung-type-c-earphones-eo-ic100-eo-ic100bbegww-530300950?$650_519_PNG$",
            "https://media.binglee.com.au/cdn-cgi/image/fit=scale-down,f=auto,w=1079/7/1/3/0/7130814e78a541bc064ab9cdef04124a156a2270_Hero1.jpg",
        ],
        desc_html="""<p>Experience premium sound quality with Samsung Type-C Earphones, expertly tuned by AKG. Featuring 2-way speakers for rich, balanced audio with deep bass and clear highs.</p>
<ul>
<li>Tuned by AKG for professional-grade sound</li>
<li>2-way speaker system with woofer and tweeter</li>
<li>USB Type-C connector for digital audio</li>
<li>Built-in DAC for high-quality sound</li>
<li>In-line remote with microphone</li>
</ul>""",
        meta_title="Samsung Type-C Earphone AKG | Gadget & Widget",
        meta_desc="Buy Samsung AKG USB-C Earphones. 2-way speakers, tuned by AKG, built-in DAC, in-line microphone. Premium sound quality. Order in Bangladesh.")

        populate_product(23, [
            "https://ishine-trade.com/wp-content/uploads/2025/02/9A-Genuine-Samsung-USB-C-To-USB-C-Cable-EP-DN980-1.webp",
        ],
        desc_html="""<p>Genuine Samsung USB-C to USB-C cable rated for 5A current. Supports Super Fast Charging 2.0 up to 45W for compatible Samsung devices. 1 meter length.</p>
<ul>
<li>5A current rating for fast charging</li>
<li>USB-C to USB-C connectors</li>
<li>Supports Super Fast Charging 2.0 up to 45W</li>
<li>1 meter length</li>
</ul>""",
        meta_title="Samsung USB-C to USB-C 5A 1M Cable | Gadget & Widget",
        meta_desc="Original Samsung USB-C to USB-C 5A 1M cable. Supports Super Fast Charging 2.0 up to 45W. Durable and reliable. Available in Bangladesh.")

        populate_product(24, [
            "https://m.media-amazon.com/images/I/61tF2RwDzCL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/715F6OOJRvL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2023/05/61JrTBa9HNL._AC_SX569_.jpg",
            "https://anker.com.bd/wp-content/uploads/2023/05/61m0B57sayL._AC_SX569_.jpg",
            "https://anker.com.bd/wp-content/uploads/2023/05/A1641031_TD01_V1_2878x-1-1024x1024.jpg",
        ],
        desc_html="""<p>Anker PowerPort III 20W Cube PD charger. Ultra-compact design with 20W Power Delivery for fast charging iPhone and Android devices. Foldable plug for easy portability.</p>
<ul>
<li>20W Power Delivery for fast charging</li>
<li>Compact cube design with foldable plug</li>
<li>Compatible with iPhone 15/14/13 series and Samsung Galaxy</li>
<li>Anker MultiProtect safety system</li>
<li>USB-C output</li>
</ul>""",
        meta_title="Anker PowerPort III 20W Cube PD Charger | Gadget & Widget",
        meta_desc="Anker PowerPort III 20W Cube PD charger. Ultra-compact, foldable plug, fast charging for iPhone & Samsung. MultiProtect safety. Buy in Bangladesh.")

        populate_product(25, [
            "https://m.media-amazon.com/images/I/71AlY1KdOBL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/71Z7lUNIjDL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2024/12/20241005_qeGBurVwmn.jpeg",
            "https://anker.com.bd/wp-content/uploads/2024/12/Anker-Zolo-20W.webp",
        ],
        desc_html="""<p>Anker Zolo 20W PD3 Adapter delivers fast charging for iPhone and Android devices. Compact design with USB-C PD and IQ technology for optimized charging.</p>
<ul>
<li>20W Power Delivery 3.0</li>
<li>Anker IQ technology for universal compatibility</li>
<li>Compact and portable design</li>
<li>MultiProtect safety system</li>
<li>USB-C output</li>
</ul>""",
        meta_title="Anker Zolo 20W PD3 Fast Charger | Gadget & Widget",
        meta_desc="Anker Zolo 20W PD3 Adapter. Fast charging for iPhone 15/14/13 and Samsung Galaxy. Compact, safe, reliable. Order online in Bangladesh.")

        populate_product(26, [
            "https://m.media-amazon.com/images/I/61Gi9Qcq40L._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/714uBMqVlXL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/717IhFBfOgL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/03/Anker-Zolo-30w-IQ-PD-Blue.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/03/Anker-Zolo-30w-IQ-PD-Blac.jpg",
        ],
        desc_html="""<p>Anker Zolo 30W Adapter provides high-speed charging for smartphones and tablets. Features Power Delivery 3.0 with PPS support for Samsung Super Fast Charging.</p>
<ul>
<li>30W Power Delivery 3.0 with PPS</li>
<li>Samsung Super Fast Charging compatible</li>
<li>Anker IQ 3.0 technology</li>
<li>Compact design</li>
<li>MultiProtect safety system</li>
<li>USB-C output</li>
</ul>""",
        meta_title="Anker Zolo 30W PD Fast Charger | Gadget & Widget",
        meta_desc="Buy Anker Zolo 30W PD Charger in Bangladesh. Fast charging with PPS support, compatible with Samsung Super Fast Charging. Safe and reliable.")

        populate_product(27, [
            "https://m.media-amazon.com/images/I/61paJLhVoaL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/71IEFaYMo3L._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/09/Anker-Nano-Charger-45W_Black_Deximpo.png",
            "https://anker.com.bd/wp-content/uploads/2025/09/Anker-Nano-Charger-45W_White_Deximpo.png",
        ],
        desc_html="""<p>Anker Nano 1C GAN Charger (45W) - Ultra-compact GaN technology charger with 45W Power Delivery. Charge your laptop, tablet, and smartphone with a single compact charger.</p>
<ul>
<li>45W Power Delivery with GaN technology</li>
<li>Ultra-compact size</li>
<li>Compatible with iPhone 15 Pro Max, Samsung Galaxy, MacBook Air</li>
<li>USB-C output</li>
<li>Anker MultiProtect safety system</li>
</ul>""",
        meta_title="Anker Nano 1C GaN 45W Fast Charger | Gadget & Widget",
        meta_desc="Anker Nano 1C GaN 45W Charger. Ultra-compact GaN technology, fast charge laptop & phone. Available in Bangladesh. Order now!")

        populate_product(28, [
            "https://m.media-amazon.com/images/I/41LHpaAzAlL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/51w24XFuiAL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/51UN7cJsKhL._AC_SL1500_.jpg",
        ],
        desc_html="""<p>Anker Nano Charger (45W, Smart Display, 180° Foldable) - Smart display shows real-time charging status. GaN technology with foldable plug for ultimate portability.</p>
<ul>
<li>45W Power Delivery with GaN technology</li>
<li>Smart display shows charging status</li>
<li>180° foldable plug for travel</li>
<li>Auto-detects connected devices</li>
<li>3-stage protection system</li>
</ul>""",
        meta_title="Anker Nano 45W Smart Display GaN Charger | Gadget & Widget",
        meta_desc="Anker Nano 45W Smart Display Charger with foldable plug. GaN tech, real-time charging status display. Fast shipping in Bangladesh.")

        populate_product(29, [
            "https://m.media-amazon.com/images/I/8104JIJwjzL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2024/12/20241005_qeGBurVwmn.jpeg",
            "https://anker.com.bd/wp-content/uploads/2024/12/Anker-Zolo-20W.webp",
        ],
        desc_html="""<p>Anker Zolo 20W Wiring Set includes a 20W PD charger and USB-C to USB-C cable. Perfect all-in-one charging solution for your iPhone, Samsung, or Android device.</p>
<ul>
<li>20W Power Delivery charger</li>
<li>Includes USB-C to USB-C cable</li>
<li>Compact travel-friendly design</li>
<li>Anker safety technology</li>
</ul>""",
        meta_title="Anker Zolo 20W Wiring Set (C to C) | Gadget & Widget",
        meta_desc="Anker Zolo 20W Wiring Set with PD charger and USB-C cable. Complete charging kit for iPhone and Android. Buy in Bangladesh.")

        populate_product(30, [
            "https://m.media-amazon.com/images/I/61Gi9Qcq40L._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/714uBMqVlXL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/03/Anker-Zolo-30w-IQ-PD-Blue.jpg",
        ],
        desc_html="""<p>Anker Zolo 30W Wiring Set includes a 30W PD charger with PPS support and USB-C to USB-C cable. Fast charging solution for Samsung Galaxy and other USB-C devices.</p>
<ul>
<li>30W Power Delivery with PPS</li>
<li>Includes USB-C to USB-C cable</li>
<li>Samsung Super Fast Charging compatible</li>
<li>Compact design</li>
</ul>""",
        meta_title="Anker Zolo 30W Wiring Set (C to C) | Gadget & Widget",
        meta_desc="Anker Zolo 30W Wiring Set with PD PPS charger and USB-C cable. Samsung Super Fast Charging compatible. Order in Bangladesh.")

        populate_product(31, [
            "https://m.media-amazon.com/images/I/61tF2RwDzCL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/715F6OOJRvL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2023/05/A1641031_TD01_V1_2878x-1-1024x1024.jpg",
        ],
        desc_html="""<p>PP3 20W Wiring Set includes PowerPort III 20W Cube PD charger and USB-C to Lightning cable. The perfect charging kit for iPhone users.</p>
<ul>
<li>20W Power Delivery for iPhone fast charging</li>
<li>Includes USB-C to Lightning cable</li>
<li>Compact cube design with foldable plug</li>
<li>MFi certified Lightning connector</li>
<li>Anker MultiProtect safety</li>
</ul>""",
        meta_title="Anker PP3 20W Cube PD with Lightning Cable | Gadget & Widget",
        meta_desc="Anker PowerPort III 20W Cube PD with USB-C to Lightning cable. iPhone fast charging kit. MFi certified. Available in Bangladesh.")

        populate_product(32, [
            "https://cdn.shopify.com/s/files/1/0785/8284/1629/files/Web_1_1730007435671dd18b2d5581523.png",
            "https://cdn.shopify.com/s/files/1/0785/8284/1629/files/Web_2_1730007454671dd19e5bbb51845.png",
        ],
        desc_html="""<p>Anker Zolo USB-C to USB-C Cable (1.5M, 240W, Braided) - Ultra-high power delivery cable supporting up to 240W for charging laptops, tablets, and smartphones. Durable braided design.</p>
<ul>
<li>240W power delivery (EPR standard)</li>
<li>USB 2.0 data transfer</li>
<li>1.5 meter length</li>
<li>Durable braided nylon exterior</li>
<li>Compatible with MacBook Pro, Dell XPS, Samsung Galaxy, iPhone 15 series</li>
</ul>""",
        meta_title="Anker Zolo USB-C to USB-C 240W Braided Cable 1.5M | Gadget & Widget",
        meta_desc="Anker Zolo 240W USB-C braided cable 1.5M. Ultra-fast charging for laptops and phones. Durable nylon braided. Buy in Bangladesh.")

        populate_product(33, [
            "https://anker.com.bd/wp-content/uploads/2025/08/4.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/08/5.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/08/2.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/08/3.jpg",
        ],
        desc_html="""<p>Anker 310 USB-C Cable With Lightning Connector - Braided cable designed for Apple devices. MFi certified for reliable, fast charging and data sync.</p>
<ul>
<li>USB-C to Lightning connector</li>
<li>Durable braided nylon design</li>
<li>MFi certified</li>
<li>Fast charging support for iPhone/iPad</li>
</ul>""",
        meta_title="Anker 310 USB-C to Lightning Braided Cable | Gadget & Widget",
        meta_desc="Anker 310 USB-C to Lightning braided cable. MFi certified, durable nylon braided, fast charging for iPhone. Available in Bangladesh.")

        populate_product(34, [
            "https://m.media-amazon.com/images/I/61GF1EnHUaL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/71lZ6KUA8IL._AC_SL1500_.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/05/Anker-Braided-100w-Cable2.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/05/Anker-Braided-100w-Cable3.jpg",
            "https://anker.com.bd/wp-content/uploads/2025/05/Anker-Braided-100w-Cable4.jpg",
        ],
        desc_html="""<p>Anker USB C to USB C Cable 100W - Premium braided USB-C cable supporting up to 100W power delivery. Perfect for charging laptops, tablets, and smartphones.</p>
<ul>
<li>100W Power Delivery</li>
<li>USB 2.0 data transfer speed</li>
<li>Durable braided nylon construction</li>
<li>Compatible with MacBook, iPad Pro, Samsung Galaxy, iPhone 15</li>
</ul>""",
        meta_title="Anker USB-C to USB-C 100W Braided Cable | Gadget & Widget",
        meta_desc="Anker USB-C to USB-C 100W braided cable. Fast charging for laptops and phones. Durable nylon design. Order in Bangladesh.")

        populate_product(35, [
            "https://baseus.com.bd/wp-content/uploads/2022/09/Baseus-Charger-20W-For-Apple-Iphone-14-13-12-11-Series-GaN5-Fast-Charger-1C-CN-Set-Black-Type-C-to-iP-PD-20W-1m-Cable-Sierra-Blue-CCGN040103-2.jpg",
            "https://baseus.com.bd/wp-content/uploads/2022/09/Baseus-Charger-20W-For-Apple-Iphone-14-13-12-11-Series-GaN5-Fast-Charger-1C-CN-Set-Black-Type-C-to-iP-PD-20W-1m-Cable-Sierra-Blue-CCGN040103-3.jpg",
            "https://baseus.com.bd/wp-content/uploads/2022/09/Baseus-Charger-20W-For-Apple-Iphone-14-13-12-11-Series-GaN5-Fast-Charger-1C-CN-Set-Black-Type-C-to-iP-PD-20W-1m-Cable-Sierra-Blue-CCGN040103-7.jpg",
            "https://baseus.com.bd/wp-content/uploads/2022/09/Baseus-Charger-20W-For-Apple-Iphone14-13-12-11-Series-GaN5-Fast-Charger-1C-CN-Set-Black-Type-C-to-iP-PD-20W-1m-Cable-Black-CCGN040101-1.jpg",
        ],
        desc_html="""<p>20W GaN5 Adapter - Next-generation GaN5 technology charger. Ultra-compact size with 20W Power Delivery for fast charging iPhone and Android devices.</p>
<ul>
<li>20W Power Delivery with GaN5 technology</li>
<li>Ultra-compact and lightweight</li>
<li>USB-C output</li>
<li>Compatible with iPhone 15/14/13 and Samsung Galaxy</li>
<li>Intelligent temperature control</li>
</ul>""",
        meta_title="20W GaN5 Fast Charger Adapter | Gadget & Widget",
        meta_desc="20W GaN5 Adapter with GaN5 technology. Ultra-compact fast charger for iPhone and Android. Available in Bangladesh.")

        populate_product(36, [],
        desc_html="""<p>Crystal Series C To IP PD Cable - Premium transparent USB-C to Lightning cable with Power Delivery support. Stylish crystal design with durable construction.</p>
<ul>
<li>USB-C to Lightning connector</li>
<li>Power Delivery fast charging</li>
<li>Stylish transparent crystal design</li>
<li>Durable construction</li>
<li>Compatible with iPhone and iPad</li>
</ul>""",
        meta_title="Crystal Series USB-C to Lightning PD Cable | Gadget & Widget",
        meta_desc="Crystal Series USB-C to Lightning PD cable. Stylish transparent design with fast charging. Compatible with iPhone. Buy in Bangladesh.")

        populate_product(37, [],
        desc_html="""<p>Cafule C To C PD2.0 60W Cable - High-speed USB-C to USB-C cable supporting 60W Power Delivery 2.0. Ideal for fast charging laptops, tablets, and smartphones.</p>
<ul>
<li>60W Power Delivery 2.0</li>
<li>USB-C to USB-C connectors</li>
<li>Fast charging and data sync</li>
<li>Durable construction</li>
<li>Compatible with MacBook, iPad Pro, Samsung Galaxy</li>
</ul>""",
        meta_title="Cafule USB-C to USB-C PD 60W Cable | Gadget & Widget",
        meta_desc="Cafule C to C PD2.0 60W cable. Fast charging for laptops and phones. USB-C to USB-C, durable design. Available in Bangladesh.")

        populate_product(38, [],
        desc_html="""<p>Smooth Writing 2 Series Stylus With LED Indicator - Precision stylus pen for touchscreen devices. Features LED battery indicator, palm rejection, and smooth writing experience.</p>
<ul>
<li>Active/passive dual modes</li>
<li>LED battery indicator</li>
<li>Palm rejection technology</li>
<li>Fine tip for precise writing and drawing</li>
<li>Rechargeable battery</li>
</ul>""",
        meta_title="Smooth Writing 2 Stylus Pen with LED Indicator | Gadget & Widget",
        meta_desc="Smooth Writing 2 Stylus Pen with LED indicator. Active/passive stylus with palm rejection. Compatible with touchscreen devices. Bangladesh.")

        populate_product(47, [
            "https://m.media-amazon.com/images/I/61iGKM45mZL._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/51W1jQ8H4VL._AC_SL1500_.jpg",
        ],
        desc_html="""<p>Pop 3S (Black & Silver) - Stylish smartwatch with AMOLED display, Bluetooth calling, and health tracking features. Modern design in black and silver.</p>
<ul>
<li>AMOLED display</li>
<li>Bluetooth calling</li>
<li>Heart rate and SpO2 monitoring</li>
<li>Multiple sports modes</li>
<li>Long battery life</li>
<li>Water resistant</li>
</ul>""",
        meta_title="Pop 3S Smartwatch Black & Silver | Gadget & Widget",
        meta_desc="Pop 3S Smartwatch with AMOLED display, Bluetooth calling, health tracking. Black & Silver. Buy in Bangladesh.")

        populate_product(48, [
            "https://mobilebuzzbd.com/wp-content/uploads/2024/05/Amazfit-Pop-3R-Metallic-Strap-Black.webp",
            "https://mobilebuzzbd.com/wp-content/uploads/2024/05/Amazfit-Pop-3R-Metallic-Strap-Black-600x600.webp",
        ],
        desc_html="""<p>Pop 3R (Black & Silver) - Feature-rich smartwatch with Bluetooth calling, health monitoring, and sleek design. Perfect for everyday wear.</p>
<ul>
<li>Bluetooth calling</li>
<li>Health monitoring (heart rate, SpO2, sleep)</li>
<li>Multiple sports modes</li>
<li>IP68 water resistance</li>
<li>7-day battery life</li>
</ul>""",
        meta_title="Pop 3R Smartwatch Black & Silver | Gadget & Widget",
        meta_desc="Pop 3R Smartwatch with Bluetooth calling, health monitoring, sports modes. Black & Silver. Available in Bangladesh.")

        populate_product(66, [],
        desc_html="""<p>HT10 Ailybuds Pro+ ANC - Premium true wireless earbuds with Active Noise Cancellation. Immersive sound quality with comfortable fit and long battery life.</p>
<ul>
<li>Active Noise Cancellation (ANC)</li>
<li>Bluetooth 5.3 connectivity</li>
<li>High-quality audio drivers</li>
<li>Touch controls</li>
<li>IPX5 water resistant</li>
<li>Up to 30 hours total playback</li>
</ul>""",
        meta_title="HT10 Ailybuds Pro+ ANC Earbuds | Gadget & Widget",
        meta_desc="HT10 Ailybuds Pro+ ANC true wireless earbuds. Active Noise Cancellation, Bluetooth 5.3, 30h battery. Buy in Bangladesh.")

        populate_product(67, [
            "https://image01-in.oneplus.net/media/202406/19/0ee6077679397b28e4dd6556c79635b3.png",
            "https://image01-in.oneplus.net/media/202406/19/1f145a88507c0cbb6383d0ee34822d5c.png",
            "https://image01-in.oneplus.net/media/202406/19/227bf8eb30a8b7436a05bdf408f014e0.png",
            "https://image01-in.oneplus.net/media/202406/19/703dc812f259ce4cb605f4602ed12301.png",
        ],
        desc_html="""<p>OnePlus Bullets Wireless Z2 ANC - Premium neckband earphones with Adaptive Noise Cancellation. Powerful bass with 12.4mm drivers and up to 20 hours of playback.</p>
<ul>
<li>Adaptive Noise Cancellation</li>
<li>12.4mm dynamic drivers</li>
<li>Bluetooth 5.0</li>
<li>Up to 20 hours battery life</li>
<li>IP55 dust and water resistant</li>
<li>Fast charging (10 min = 20 hours)</li>
<li>Magnetic earbuds with auto play/pause</li>
</ul>""",
        meta_title="OnePlus Bullets Wireless Z2 ANC | Gadget & Widget",
        meta_desc="OnePlus Bullets Wireless Z2 ANC neckband earphones. Adaptive ANC, 12.4mm drivers, 20h battery, IP55. Buy in Bangladesh.")

        populate_product(68, [
            "https://cdn.shopify.com/s/files/1/0571/8648/4422/files/1464-1_2a64798b-4fb0-413c-aff5-62609759b337.jpg",
            "https://cdn.shopify.com/s/files/1/0571/8648/4422/files/1464-2_c28b87f4-5171-460f-8af4-7fcf0e9f3cfe.jpg",
            "https://cdn.shopify.com/s/files/1/0571/8648/4422/files/1464-3_d7903c52-d022-4c28-995c-2f1089d3eb38.jpg",
            "https://cdn.shopify.com/s/files/1/0571/8648/4422/files/1_b19ae674-a50c-43a3-944b-3cc4d957b09e.jpg",
            "https://cdn.shopify.com/s/files/1/0571/8648/4422/files/2_393ffa1f-9320-4524-8276-6106b907e4e3.jpg",
        ],
        desc_html="""<p>TELESIN FUN SHOT MAGNETIC GRIP - Versatile magnetic grip for action cameras. Quick-release magnetic mount for GoPro and other action cameras. Perfect for vlogging and POV shots.</p>
<ul>
<li>Magnetic quick-release design</li>
<li>Compatible with GoPro and most action cameras</li>
<li>Ergonomic grip handle</li>
<li>1/4 inch screw mount</li>
<li>Durable construction</li>
</ul>""",
        meta_title="TELESIN FUN SHOT Magnetic Grip for Action Camera | Gadget & Widget",
        meta_desc="TELESIN FUN SHOT Magnetic Grip for GoPro and action cameras. Quick-release magnetic mount, ergonomic handle. Available in Bangladesh.")

        self.stdout.write(self.style.SUCCESS("\n\nAll remaining products populated successfully!"))
