import pandas as pd
from app import create_app
from app.extensions import db
from app.model import Product

# Create an app instance
app = create_app()

# Use the app's context to access the database
with app.app_context():
    # Query all products from the database
    products = Product.query.all()

    # Convert the products to a list of dictionaries
    product_data = [
        {
            "ID": product.id,
            "Barcode": product.barcode,
            "Slug": product.slug,
            "Name": product.name,
            "Code": product.code,
            "Price": product.price,
            "Quantity": product.quantity,
            "Minimum Order": product.minimum_order,
            "Subtract Stock": product.subtract_stock,
            "Out of Stock Status": product.out_of_stock_status,
            "Date Available": product.date_available,
            "Status": product.status,
            "Is New": product.is_new,
            "Viewed": product.viewed,
            "Is Favourite": product.is_favourite,
            "Reviewable": product.reviewable,
            "Unit": product.unit,
            "EAN Code": product.ean_code,
            "Category ID": product.category_id,
            "Created At": product.created_at,
            "Updated At": product.updated_at
        }
        for product in products
    ]

    # Convert the list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(product_data)

    # Export to Excel
    excel_file_path = "/Users/davidlong/Desktop/pintel_api/instance/products_export.xlsx"
    df.to_excel(excel_file_path, index=False)

    print(f"Products have been exported to Excel at {excel_file_path}")
