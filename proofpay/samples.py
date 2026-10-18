"""Sample deliverables so judges can run the full flow in two minutes."""

M1_GOOD = """# Sweet Crumbs - wireframe & copy

## Sections
1. **Hero** - full-width photo of a chocolate truffle cake
   - Headline: "Baked fresh in Vijayawada, every single morning"
   - Call to action button: "Order now" (scrolls to the order section)
2. **Menu** - cards in a 3-column grid
3. **About** - "Started in Lakshmi's kitchen in 2019..."
4. **Order** - pickup order form (milestone 3)
5. **Contact** - phone, address, hours, Instagram link

## Menu copy
| Item | Price |
|---|---|
| Chocolate truffle cake (500 g) | ₹650 |
| Red velvet cake (500 g) | ₹700 |
| Butter cookies (box of 12) | ₹220 |
| Walnut brownies (box of 6) | ₹300 |
| Banana bread loaf | ₹260 |
| Custom birthday cake | from ₹1,200 |
"""

M2_WEAK = """<!doctype html>
<html>
<head>
  <title>Sweet Crumbs Bakery</title>
  <style>
    body { font-family: Georgia, serif; width: 1200px; margin: 0 auto; }
    .hero { height: 600px; background: url(cake.jpg); }
    .menu-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
  </style>
</head>
<body>
  <section class="hero">
    <h1>Baked fresh in Vijayawada, every single morning</h1>
    <a class="btn" href="#order">Order now</a>
  </section>
  <section id="menu" class="menu-grid">
    <div><img src="truffle.jpg"><h3>Chocolate truffle cake</h3></div>
    <div><img src="velvet.jpg"><h3>Red velvet cake</h3></div>
    <div><img src="cookies.jpg"><h3>Butter cookies</h3></div>
  </section>
  <section id="about"><p>Started in Lakshmi's kitchen in 2019.</p></section>
</body>
</html>
"""

M2_GOOD = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sweet Crumbs Bakery</title>
  <style>
    body { font-family: Georgia, serif; max-width: 1200px; margin: 0 auto; }
    .hero { min-height: 60vh; background: url(cake.jpg) center/cover; }
    .menu-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
    @media (max-width: 640px) {
      .menu-grid { grid-template-columns: 1fr; }
      .hero h1 { font-size: 1.8rem; }
    }
  </style>
</head>
<body>
  <section class="hero">
    <h1>Baked fresh in Vijayawada, every single morning</h1>
    <a class="btn" href="#order">Order now</a>
  </section>
  <section id="menu" class="menu-grid">
    <div><img src="truffle.jpg" alt="Chocolate truffle cake"><h3>Chocolate truffle cake</h3><p>₹650</p></div>
    <div><img src="velvet.jpg" alt="Red velvet cake"><h3>Red velvet cake</h3><p>₹700</p></div>
    <div><img src="cookies.jpg" alt="Box of butter cookies"><h3>Butter cookies (12)</h3><p>₹220</p></div>
  </section>
  <section id="about"><p>Started in Lakshmi's kitchen in 2019.</p></section>
  <section id="contact">
    <h2>Contact</h2>
    <p>Phone: <a href="tel:+919800012345">+91 98000 12345</a></p>
    <p>Address: 12-4-7 Benz Circle, Vijayawada, Andhra Pradesh</p>
    <p>Open Tue-Sun, 9 am - 8 pm</p>
  </section>
</body>
</html>
"""

M3_GOOD = """Deployed at: https://sweetcrumbs-demo.onrender.com

<form id="order">
  <select name="item"><option>Chocolate truffle cake</option></select>
  <input type="number" name="quantity" min="1" value="1">
  <input type="time" name="pickup" required>
  <div id="paypal-button-container"></div>
</form>
<script src="https://www.paypal.com/sdk/js?client-id=SANDBOX_ID&currency=USD"></script>
<script>
  paypal.Buttons({
    createOrder: () => fetch('/api/orders', {method: 'POST'}).then(r => r.json()).then(o => o.id),
    onApprove: (data) => fetch(`/api/orders/${data.orderID}/capture`, {method: 'POST'})
  }).render('#paypal-button-container');
</script>
"""

SAMPLES = {
    1: {"Good submission": M1_GOOD},
    2: {"Weak first attempt": M2_WEAK, "Fixed submission": M2_GOOD},
    3: {"Good submission": M3_GOOD},
}
