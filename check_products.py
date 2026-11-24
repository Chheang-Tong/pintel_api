from app import create_app
from app.extensions import db
from app.model import Product

# Create an app instance
app = create_app()

# Use the app's context to access the database
with app.app_context():
    # Query all products from the database
    products = Product.query.all()

    # Print the details of each product
    for product in products:
        print(f"ID: {product.id}")
        print(f"Name: {product.name}")
        print(f"Barcode: {product.barcode}")
        print(f"Code: {product.code}")
        print(f"Price: {product.price}")
        print(f"Quantity: {product.quantity}")
        print(f"Category ID: {product.category_id}")
        print(f"Created At: {product.created_at}")
        print(f"Updated At: {product.updated_at}")
        print("=" * 50)  # Separator for clarity
