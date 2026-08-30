import asyncio
from app.database import async_engine, Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import (
    RawMaterial, Supplier, SupplierMaterial, ProductBOM,
    Factory, TransportRoute, DeliverySchedule
)

AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with async_engine.begin() as conn:
        # Create all tables
        print("Creating tables...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created.")

async def seed_data():
    async with AsyncSessionLocal() as session:
        # 1. Raw Materials
        materials = [
            RawMaterial(name="Grade-A Wheat Flour", category="Grain", current_stock=5000.0, unit="kg", reorder_level=1000.0, daily_consumption_rate=500.0, shelf_life_days=180),
            RawMaterial(name="Refined Sugar", category="Sweetener", current_stock=3000.0, unit="kg", reorder_level=500.0, daily_consumption_rate=300.0, shelf_life_days=365),
            RawMaterial(name="Palm Oil", category="Fat", current_stock=2000.0, unit="liters", reorder_level=500.0, daily_consumption_rate=200.0, shelf_life_days=180),
            RawMaterial(name="Baking Powder", category="Additives", current_stock=100.0, unit="kg", reorder_level=20.0, daily_consumption_rate=5.0, shelf_life_days=365),
        ]
        session.add_all(materials)
        await session.commit()
        
        # 2. Suppliers
        suppliers = [
            Supplier(name="Regional Agro Farms", contact_email="sales@regionalagro.com", location_region="North (Delhi/NCR)", lead_time_days=3, reliability_score=0.95),
            Supplier(name="National Cash & Carry", contact_email="orders@nationalcash.com", location_region="South (Bangalore)", lead_time_days=1, reliability_score=0.98),
            Supplier(name="SweetLife Sugar Co.", contact_email="sales@sweetlife.com", location_region="East (Kolkata)", lead_time_days=5, reliability_score=0.92),
            Supplier(name="OilTech Distributors", contact_email="logistics@oiltech.com", location_region="West (Mumbai)", lead_time_days=4, reliability_score=0.90),
        ]
        session.add_all(suppliers)
        await session.commit()
        
        # 3. Supplier Material Mappings
        mappings = [
            SupplierMaterial(supplier_id=1, material_id=1, unit_price=1.20, is_primary=True), # Wheat - Primary (North)
            SupplierMaterial(supplier_id=2, material_id=1, unit_price=1.50, is_primary=False), # Wheat - Backup (South)
            
            SupplierMaterial(supplier_id=3, material_id=2, unit_price=0.80, is_primary=True), # Sugar - Primary (East)
            SupplierMaterial(supplier_id=2, material_id=2, unit_price=1.00, is_primary=False), # Sugar - Backup (South)
            
            SupplierMaterial(supplier_id=4, material_id=3, unit_price=2.00, is_primary=True), # Oil - Primary (West)
            SupplierMaterial(supplier_id=2, material_id=3, unit_price=2.40, is_primary=False), # Oil - Backup (South)
            
            SupplierMaterial(supplier_id=2, material_id=4, unit_price=5.00, is_primary=True), # Baking Powder - Primary (South)
        ]
        session.add_all(mappings)
        await session.commit()
        
        # 4. Product BOM
        boms = [
            ProductBOM(product_name="Cream Biscuit", material_id=1, required_quantity_per_unit=0.5),
            ProductBOM(product_name="Cream Biscuit", material_id=2, required_quantity_per_unit=0.2),
            ProductBOM(product_name="Cream Biscuit", material_id=3, required_quantity_per_unit=0.1),
            ProductBOM(product_name="Cream Biscuit", material_id=4, required_quantity_per_unit=0.01),
        ]
        session.add_all(boms)
        await session.commit()

        # 5. Factory
        factory = Factory(
            name="Chennai Central Biscuit Plant", 
            city="Chennai", 
            region="South",
            operating_hours_start="06:00",
            operating_hours_end="22:00",
            receiving_window_start="08:00",
            receiving_window_end="17:00" # Deliveries after 5 PM are rejected until next day
        )
        session.add(factory)
        await session.commit()

        # 6. Transport Routes (To Chennai Factory)
        routes = [
            TransportRoute( # North to South (Wheat)
                supplier_id=1, factory_id=factory.factory_id, route_name="Delhi-Chennai Express Route",
                key_highways="NH-44", key_cities_passed="Delhi, Agra, Nagpur, Hyderabad, Bangalore, Chennai",
                distance_km=2180, normal_transit_hours=48
            ),
            TransportRoute( # South to South (Backup)
                supplier_id=2, factory_id=factory.factory_id, route_name="Bangalore-Chennai Freight Corridor",
                key_highways="NH-48", key_cities_passed="Bangalore, Hosur, Vellore, Chennai",
                distance_km=350, normal_transit_hours=8
            ),
            TransportRoute( # East to South (Sugar)
                supplier_id=3, factory_id=factory.factory_id, route_name="East Coast Sugar Route",
                key_highways="NH-16", key_cities_passed="Kolkata, Bhubaneswar, Visakhapatnam, Vijayawada, Chennai",
                distance_km=1670, normal_transit_hours=36
            ),
            TransportRoute( # West to South (Oil)
                supplier_id=4, factory_id=factory.factory_id, route_name="Western Ghats Transit",
                key_highways="NH-48, NH-65", key_cities_passed="Mumbai, Pune, Belagavi, Hubballi, Bangalore, Chennai",
                distance_km=1330, normal_transit_hours=30
            )
        ]
        session.add_all(routes)
        await session.commit()

        # 7. Delivery Schedules
        schedules = [
            # Wheat from North (arrives Mon/Wed/Fri at 14:00)
            DeliverySchedule(route_id=1, material_id=1, delivery_day="Monday", expected_departure_time="14:00", expected_arrival_time="14:00"),
            DeliverySchedule(route_id=1, material_id=1, delivery_day="Wednesday", expected_departure_time="14:00", expected_arrival_time="14:00"),
            DeliverySchedule(route_id=1, material_id=1, delivery_day="Friday", expected_departure_time="14:00", expected_arrival_time="14:00"),
            
            # Sugar from East (arrives Tue/Thu at 10:00)
            DeliverySchedule(route_id=3, material_id=2, delivery_day="Tuesday", expected_departure_time="22:00", expected_arrival_time="10:00"),
            DeliverySchedule(route_id=3, material_id=2, delivery_day="Thursday", expected_departure_time="22:00", expected_arrival_time="10:00"),
            
            # Oil from West (arrives Mon/Thu at 16:00 - Close to the 17:00 cutoff!)
            DeliverySchedule(route_id=4, material_id=3, delivery_day="Monday", expected_departure_time="10:00", expected_arrival_time="16:00"),
            DeliverySchedule(route_id=4, material_id=3, delivery_day="Thursday", expected_departure_time="10:00", expected_arrival_time="16:00"),
        ]
        session.add_all(schedules)
        await session.commit()

        print("Data seeded successfully with factories, routes, and schedules!")

async def main():
    await init_db()
    await seed_data()

if __name__ == "__main__":
    asyncio.run(main())
