import pandas as pd
from app import create_app
from app.extensions import db
from app.model import Product

# Path to your Excel file
excel_file_path = "/Users/davidlong/Desktop/pintel_api/instance/products_import.xlsx"

# Create an app instance
app = create_app()

# Use the app's context to access the database
with app.app_context():
    # Read the Excel file into a pandas DataFrame
    df = pd.read_excel(excel_file_path)

    # Print column names for debugging
    print("Excel Columns:", df.columns)

    # Clean column names (remove extra spaces)
    df.columns = df.columns.str.strip()

    # Iterate through each row in the DataFrame and add to the database
    for _, row in df.iterrows():
        # Check if 'Is Pin' exists in the Excel columns, if not, set to False
        is_pin = row['Is Pin'] if 'Is Pin' in df.columns else False

        # Prepare product data
        product_data = {
            "barcode": row['Barcode'],
            "slug": row['Slug'],
            "name": row['Name'],
            "code": row['Code'],
            "price": row['Price'],
            "is_pin": is_pin,  # Use the default value if 'Is Pin' is missing
            "price_format": f"${row['Price']:.2f}",  # Format price as a string (e.g., $25.99)
            "quantity": row['Quantity'],
            "minimum_order": row['Minimum Order'],
            "subtract_stock": row['Subtract Stock'],
            "out_of_stock_status": row['Out of Stock Status'],
            "date_available": row['Date Available'],
            "status": row['Status'],
            "is_new": row['Is New'],
            "viewed": row['Viewed'],
            "is_favourite": row['Is Favourite'],
            "reviewable": row['Reviewable'],
            "unit": row['Unit'],
            "ean_code": row['EAN Code'],
            "category_id": row['Category ID'],
        }

        # Create Product instance
        product = Product(**product_data)
        db.session.add(product)

    # Commit the changes to the database
    db.session.commit()

    print(f"{len(df)} products have been imported successfully from {excel_file_path}")
