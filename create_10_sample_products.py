from app import create_app
from app.extensions import db
from app.model import Product

# Create an app instance
app = create_app()

# Sample products to insert into the database
sample_products = [
    {"barcode": "1234567890", "slug": "product-1", "name": "Sample Product 1", "code": "P001", "price": 20.99, "is_pin": False, "price_format": "$20.99", "quantity": 100, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": True, "viewed": 0, "is_favourite": False, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567890", "category_id": 1},
    {"barcode": "1234567891", "slug": "product-2", "name": "Sample Product 2", "code": "P002", "price": 15.99, "is_pin": True, "price_format": "$15.99", "quantity": 150, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": False, "viewed": 5, "is_favourite": True, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567891", "category_id": 1},
    {"barcode": "1234567892", "slug": "product-3", "name": "Sample Product 3", "code": "P003", "price": 10.50, "is_pin": False, "price_format": "$10.50", "quantity": 200, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": True, "viewed": 0, "is_favourite": False, "reviewable": False, "unit": "pcs", "ean_code": "EAN001234567892", "category_id": 1},
    {"barcode": "1234567893", "slug": "product-4", "name": "Sample Product 4", "code": "P004", "price": 12.75, "is_pin": True, "price_format": "$12.75", "quantity": 50, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": False, "viewed": 10, "is_favourite": True, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567893", "category_id": 1},
    {"barcode": "1234567894", "slug": "product-5", "name": "Sample Product 5", "code": "P005", "price": 8.99, "is_pin": False, "price_format": "$8.99", "quantity": 120, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": False, "viewed": 3, "is_favourite": False, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567894", "category_id": 1},
    {"barcode": "1234567895", "slug": "product-6", "name": "Sample Product 6", "code": "P006", "price": 5.50, "is_pin": True, "price_format": "$5.50", "quantity": 250, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": True, "viewed": 0, "is_favourite": True, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567895", "category_id": 1},
    {"barcode": "1234567896", "slug": "product-7", "name": "Sample Product 7", "code": "P007", "price": 18.49, "is_pin": False, "price_format": "$18.49", "quantity": 80, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": False, "viewed": 7, "is_favourite": False, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567896", "category_id": 1},
    {"barcode": "1234567897", "slug": "product-8", "name": "Sample Product 8", "code": "P008", "price": 22.99, "is_pin": True, "price_format": "$22.99", "quantity": 90, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": True, "viewed": 2, "is_favourite": True, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567897", "category_id": 1},
    {"barcode": "1234567898", "slug": "product-9", "name": "Sample Product 9", "code": "P009", "price": 14.49, "is_pin": False, "price_format": "$14.49", "quantity": 110, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": False, "viewed": 6, "is_favourite": False, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567898", "category_id": 1},
    {"barcode": "1234567899", "slug": "product-10", "name": "Sample Product 10", "code": "P010", "price": 13.20, "is_pin": True, "price_format": "$13.20", "quantity": 130, "minimum_order": 1, "subtract_stock": "yes", "out_of_stock_status": "in_stock", "date_available": "2025-10-14", "sort_order": 0, "status": True, "is_new": True, "viewed": 0, "is_favourite": True, "reviewable": True, "unit": "pcs", "ean_code": "EAN001234567899", "category_id": 1}
]

# Use the app's context to access the database
with app.app_context():
    # Insert the sample products into the database
    for product_data in sample_products:
        product = Product(**product_data)
        db.session.add(product)

    # Commit the changes to the database
    db.session.commit()

print("10 sample products have been added to the database successfully.")
