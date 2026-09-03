import asyncio
from app.database import async_engine, Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import (
    RawMaterial, Supplier, SupplierMaterial, Product, ProductBOM,
    Factory, TransportRoute, DeliverySchedule
)

AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with async_engine.begin() as conn:
        print("Creating tables...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created.")

async def seed_data():
    async with AsyncSessionLocal() as session:
        # 1. Raw Materials (Extended List)
        materials = [
            RawMaterial(name="Grade-A Wheat Flour", category="Grain", current_stock=5000.0, unit="kg", reorder_level=1000.0, daily_consumption_rate=500.0, shelf_life_days=180),
            RawMaterial(name="Refined Sugar", category="Sweetener", current_stock=3000.0, unit="kg", reorder_level=500.0, daily_consumption_rate=300.0, shelf_life_days=365),
            RawMaterial(name="Palm Oil", category="Fat", current_stock=2000.0, unit="liters", reorder_level=500.0, daily_consumption_rate=200.0, shelf_life_days=180),
            RawMaterial(name="Baking Powder", category="Additives", current_stock=100.0, unit="kg", reorder_level=20.0, daily_consumption_rate=5.0, shelf_life_days=365),
            RawMaterial(name="Cocoa Powder", category="Flavor", current_stock=160.0, unit="kg", reorder_level=200.0, daily_consumption_rate=80.0, shelf_life_days=180),
            RawMaterial(name="Whole Wheat", category="Grain", current_stock=4000.0, unit="kg", reorder_level=800.0, daily_consumption_rate=400.0, shelf_life_days=180),
            RawMaterial(name="Vanilla Extract", category="Flavor", current_stock=50.0, unit="liters", reorder_level=10.0, daily_consumption_rate=2.0, shelf_life_days=365),
        ]
        session.add_all(materials)
        await session.commit()
        
        # 2. Suppliers (More comprehensive for multiple backups)
        suppliers = [
            Supplier(name="Regional Agro Farms", contact_email="sales@regionalagro.com", location_region="North (Delhi/NCR)", lead_time_days=4, reliability_score=0.95),
            Supplier(name="National Cash & Carry", contact_email="orders@nationalcash.com", location_region="South (Bangalore)", lead_time_days=1, reliability_score=0.98),
            Supplier(name="SweetLife Sugar Co.", contact_email="sales@sweetlife.com", location_region="East (Kolkata)", lead_time_days=6, reliability_score=0.92),
            Supplier(name="OilTech Distributors", contact_email="logistics@oiltech.com", location_region="West (Mumbai)", lead_time_days=4, reliability_score=0.90),
            Supplier(name="Global Additives Inc.", contact_email="orders@globaladditives.com", location_region="West (Pune)", lead_time_days=3, reliability_score=0.94),
            Supplier(name="AgriCorp Logistics", contact_email="supply@agricorp.com", location_region="Central (Nagpur)", lead_time_days=2, reliability_score=0.88),
            Supplier(name="Southern Spice & Extracts", contact_email="sales@southernspice.com", location_region="South (Chennai)", lead_time_days=1, reliability_score=0.99),
            Supplier(name="Cocoa Imports Ltd", contact_email="import@cocoaltd.com", location_region="West (Mumbai Port)", lead_time_days=5, reliability_score=0.91),
        ]
        session.add_all(suppliers)
        await session.commit()
        
        # 3. Supplier Material Mappings (1 Primary + 2 Backups per material)
        mappings = [
            # Wheat Flour (Primary: North, Backup 1: Central, Backup 2: South)
            SupplierMaterial(supplier_id=1, material_id=1, unit_price=1.20, is_primary=True),
            SupplierMaterial(supplier_id=6, material_id=1, unit_price=1.35, is_primary=False),
            SupplierMaterial(supplier_id=2, material_id=1, unit_price=1.80, is_primary=False),
            
            # Sugar (Primary: East, Backup 1: Central, Backup 2: South)
            SupplierMaterial(supplier_id=3, material_id=2, unit_price=0.80, is_primary=True),
            SupplierMaterial(supplier_id=6, material_id=2, unit_price=0.95, is_primary=False),
            SupplierMaterial(supplier_id=2, material_id=2, unit_price=1.30, is_primary=False),
            
            # Palm Oil (Primary: West, Backup 1: Central, Backup 2: South)
            SupplierMaterial(supplier_id=4, material_id=3, unit_price=2.00, is_primary=True),
            SupplierMaterial(supplier_id=6, material_id=3, unit_price=2.30, is_primary=False),
            SupplierMaterial(supplier_id=2, material_id=3, unit_price=2.80, is_primary=False),
            
            # Baking Powder (Primary: West(Pune), Backup 1: North, Backup 2: South)
            SupplierMaterial(supplier_id=5, material_id=4, unit_price=5.00, is_primary=True),
            SupplierMaterial(supplier_id=1, material_id=4, unit_price=5.50, is_primary=False),
            SupplierMaterial(supplier_id=2, material_id=4, unit_price=7.00, is_primary=False),
            
            # Cocoa Powder
            SupplierMaterial(supplier_id=8, material_id=5, unit_price=8.00, is_primary=True),
            SupplierMaterial(supplier_id=5, material_id=5, unit_price=9.50, is_primary=False),
            SupplierMaterial(supplier_id=7, material_id=5, unit_price=12.00, is_primary=False),
            
            # Whole Wheat
            SupplierMaterial(supplier_id=1, material_id=6, unit_price=1.40, is_primary=True),
            SupplierMaterial(supplier_id=6, material_id=6, unit_price=1.60, is_primary=False),
            SupplierMaterial(supplier_id=2, material_id=6, unit_price=2.00, is_primary=False),
            
            # Vanilla Extract
            SupplierMaterial(supplier_id=7, material_id=7, unit_price=45.00, is_primary=True),
            SupplierMaterial(supplier_id=5, material_id=7, unit_price=48.00, is_primary=False),
            SupplierMaterial(supplier_id=2, material_id=7, unit_price=55.00, is_primary=False),
        ]
        session.add_all(mappings)
        await session.commit()
        
        # 4. Products (4 Products)
        products = [
            Product(name="Cream Biscuit", product_type="BISCUIT", selling_price=15.0, daily_demand=2000.0, current_finished_stock=10000.0, shelf_life_days=30, production_capacity_per_day=3000.0),
            Product(name="Chocolate Chip Cookies", product_type="COOKIE", selling_price=25.0, daily_demand=1500.0, current_finished_stock=5000.0, shelf_life_days=45, production_capacity_per_day=2000.0),
            Product(name="Digestive Biscuits", product_type="BISCUIT", selling_price=20.0, daily_demand=1200.0, current_finished_stock=6000.0, shelf_life_days=60, production_capacity_per_day=1500.0),
            Product(name="Wafer Rolls", product_type="WAFER", selling_price=30.0, daily_demand=800.0, current_finished_stock=3000.0, shelf_life_days=45, production_capacity_per_day=1000.0)
        ]
        session.add_all(products)
        await session.commit()

        # 5. Product BOM (Complex linking)
        boms = [
            # Cream Biscuit (Wheat, Sugar, Palm Oil)
            ProductBOM(product_id=1, material_id=1, quantity_per_unit=0.4, unit="kg"),
            ProductBOM(product_id=1, material_id=2, quantity_per_unit=0.2, unit="kg"),
            ProductBOM(product_id=1, material_id=3, quantity_per_unit=0.1, unit="liters"),
            
            # Chocolate Chip Cookies (Wheat, Sugar, Cocoa, Baking Powder, Palm Oil)
            ProductBOM(product_id=2, material_id=1, quantity_per_unit=0.3, unit="kg"),
            ProductBOM(product_id=2, material_id=2, quantity_per_unit=0.25, unit="kg"),
            ProductBOM(product_id=2, material_id=3, quantity_per_unit=0.1, unit="liters"),
            ProductBOM(product_id=2, material_id=4, quantity_per_unit=0.01, unit="kg"),
            ProductBOM(product_id=2, material_id=5, quantity_per_unit=0.15, unit="kg"),
            
            # Digestive Biscuits (Whole Wheat, Palm Oil, Sugar, Baking Powder)
            ProductBOM(product_id=3, material_id=6, quantity_per_unit=0.5, unit="kg"),
            ProductBOM(product_id=3, material_id=2, quantity_per_unit=0.1, unit="kg"),
            ProductBOM(product_id=3, material_id=3, quantity_per_unit=0.1, unit="liters"),
            ProductBOM(product_id=3, material_id=4, quantity_per_unit=0.01, unit="kg"),
            
            # Wafer Rolls (Wheat, Sugar, Palm Oil, Vanilla)
            ProductBOM(product_id=4, material_id=1, quantity_per_unit=0.2, unit="kg"),
            ProductBOM(product_id=4, material_id=2, quantity_per_unit=0.3, unit="kg"),
            ProductBOM(product_id=4, material_id=3, quantity_per_unit=0.05, unit="liters"),
            ProductBOM(product_id=4, material_id=7, quantity_per_unit=0.005, unit="liters"),
        ]
        session.add_all(boms)
        await session.commit()

        # 6. Factory
        factory = Factory(
            name="Chennai Central Manufacturing", 
            city="Chennai", 
            region="South",
            operating_hours_start="06:00",
            operating_hours_end="22:00",
            receiving_window_start="08:00",
            receiving_window_end="17:00"
        )
        session.add(factory)
        await session.commit()

        # 7. Transport Routes
        routes = [
            TransportRoute(supplier_id=1, factory_id=factory.factory_id, route_name="Delhi-Chennai", key_highways="NH-44", key_cities_passed="Delhi, Agra, Nagpur, Hyderabad, Bangalore, Chennai", distance_km=2180, normal_transit_hours=48),
            TransportRoute(supplier_id=2, factory_id=factory.factory_id, route_name="Bangalore-Chennai", key_highways="NH-48", key_cities_passed="Bangalore, Hosur, Vellore, Chennai", distance_km=350, normal_transit_hours=8),
            TransportRoute(supplier_id=3, factory_id=factory.factory_id, route_name="Kolkata-Chennai", key_highways="NH-16", key_cities_passed="Kolkata, Bhubaneswar, Visakhapatnam, Vijayawada, Chennai", distance_km=1670, normal_transit_hours=36),
            TransportRoute(supplier_id=4, factory_id=factory.factory_id, route_name="Mumbai-Chennai", key_highways="NH-48, NH-65", key_cities_passed="Mumbai, Pune, Belagavi, Hubballi, Bangalore, Chennai", distance_km=1330, normal_transit_hours=30),
            TransportRoute(supplier_id=5, factory_id=factory.factory_id, route_name="Pune-Chennai", key_highways="NH-48", key_cities_passed="Pune, Belagavi, Hubballi, Bangalore, Chennai", distance_km=1190, normal_transit_hours=24),
            TransportRoute(supplier_id=6, factory_id=factory.factory_id, route_name="Nagpur-Chennai", key_highways="NH-44", key_cities_passed="Nagpur, Hyderabad, Bangalore, Chennai", distance_km=1090, normal_transit_hours=20),
            TransportRoute(supplier_id=7, factory_id=factory.factory_id, route_name="Local Chennai", key_highways="Local", key_cities_passed="Chennai", distance_km=50, normal_transit_hours=2),
            TransportRoute(supplier_id=8, factory_id=factory.factory_id, route_name="Mumbai Port-Chennai", key_highways="NH-48", key_cities_passed="Mumbai, Pune, Belagavi, Bangalore, Chennai", distance_km=1340, normal_transit_hours=32),
        ]
        session.add_all(routes)
        await session.commit()

        print("Data seeded successfully with factories, routes, products, and schedules!")

async def main():
    await init_db()
    await seed_data()

if __name__ == "__main__":
    asyncio.run(main())
