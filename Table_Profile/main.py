"""
Example usage of Table Profile Graph
"""

import sys
import json
import duckdb

from table_profile_graph import (
    MetadataCollector,
    ProfilerConfig,
    load_table_from_csv,
    get_summary,
    print_report
)


def main():
    """Main example function"""
    conn = duckdb.connect(":memory:")
    
    if len(sys.argv) > 1:
        # Load CSV from command line argument
        csv_path = sys.argv[1]
        table_name = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            table_name = load_table_from_csv(conn, csv_path, table_name)
            
            # Create collector with default config
            collector = MetadataCollector(conn, table_name)
            metadata = collector.collect()
            
            # Print human-readable report
            print_report(metadata)
            
            # Save JSON summary
            output_file = f"{table_name}_metadata.json"
            summary = get_summary(metadata)
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"\n✓ Metadata saved to: {output_file}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print("\nUsage: python example.py <csv_path> [table_name]")
    
    else:
        # Run with sample data
        print("Running with enhanced sample data...\n")
        
        # Create a more comprehensive sample table
        conn.execute("""
            CREATE TABLE sales (
                order_id INTEGER,
                customer_id INTEGER,
                order_date DATE,
                product_category VARCHAR,
                product_name VARCHAR,
                quantity INTEGER,
                unit_price DECIMAL(10,2),
                total_amount DECIMAL(10,2),
                discount_percentage INTEGER,
                is_shipped BOOLEAN,
                shipping_date TIMESTAMP,
                customer_email VARCHAR,
                tracking_uuid VARCHAR,
                notes TEXT
            )
        """)
        
        # Insert richer sample data
        conn.execute("""
            INSERT INTO sales VALUES
                (1, 101, '2024-01-15', 'Electronics', 'Laptop', 1, 999.99, 999.99, 0, true, '2024-01-16 10:30:00', 'john@email.com', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'Urgent delivery'),
                (2, 102, '2024-01-16', 'Clothing', 'T-Shirt', 3, 19.99, 59.97, 10, true, '2024-01-17 14:20:00', 'jane@email.com', 'b2c3d4e5-f6a7-8901-bcde-f12345678901', NULL),
                (3, 101, '2024-01-17', 'Electronics', 'Mouse', 2, 24.99, 49.98, 0, false, NULL, 'john@email.com', 'c3d4e5f6-a7b8-9012-cdef-123456789012', 'Gift wrap requested'),
                (4, 103, '2024-01-18', 'Home', 'Lamp', 1, 45.50, 45.50, 5, true, '2024-01-19 09:15:00', 'bob@email.com', 'd4e5f6a7-b8c9-0123-def1-234567890123', NULL),
                (5, 102, '2024-01-19', 'Electronics', 'Keyboard', 1, 79.99, 79.99, 0, true, '2024-01-20 11:45:00', 'jane@email.com', 'e5f6a7b8-c9d0-1234-ef12-345678901234', 'Standard shipping'),
                (6, 104, '2024-01-20', 'Clothing', 'Jeans', 2, 49.99, 99.98, 15, false, NULL, 'alice@email.com', 'f6a7b8c9-d0e1-2345-f123-456789012345', NULL),
                (7, 103, '2024-01-21', 'Home', 'Pillow', 4, 15.99, 63.96, 0, true, '2024-01-22 16:30:00', 'bob@email.com', 'a7b8c9d0-e1f2-3456-1234-567890123456', 'Multiple items'),
                (8, 105, '2024-01-22', 'Electronics', 'Headphones', 1, 149.99, 149.99, 10, true, '2024-01-23 08:20:00', 'carol@email.com', 'b8c9d0e1-f2a3-4567-2345-678901234567', 'Express delivery'),
                (9, 101, '2024-01-23', 'Home', 'Chair', -1, 89.99, -89.99, 0, false, NULL, 'john@email.com', 'c9d0e1f2-a3b4-5678-3456-789012345678', 'Return'),
                (10, 106, '2024-01-24', 'Electronics', 'Tablet', 1, 299.99, 299.99, 5, true, '2024-01-25 13:45:00', 'dave@email.com', 'd0e1f2a3-b4c5-6789-4567-890123456789', NULL)
        """)
        
        collector = MetadataCollector(conn, "sales")
        metadata = collector.collect()
        
        # Print report
        print_report(metadata)
        
        # Save JSON
        output_file = "sales_metadata.json"
        summary = get_summary(metadata)
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✓ Metadata saved to: {output_file}")
        
        print(f"\n{'='*80}")
        print("To test with your own CSV:")
        print("python example.py <path_to_csv> [optional_table_name]")
        print(f"{'='*80}")
    
    conn.close()


if __name__ == "__main__":
    main()

