import asyncio
from app.database import async_engine, Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import RawMaterial, Supplier, SupplierMaterial, ProductBOM

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
            Supplier(name="Regional Agro Farms", contact_email="sales@regionalagro.com", location_region="North", lead_time_days=3, reliability_score=0.95),
            Supplier(name="National Cash & Carry", contact_email="orders@nationalcash.com", location_region="South", lead_time_days=1, reliability_score=0.98),
            Supplier(name="SweetLife Sugar Co.", contact_email="sales@sweetlife.com", location_region="East", lead_time_days=5, reliability_score=0.92),
            Supplier(name="OilTech Distributors", contact_email="logistics@oiltech.com", location_region="West", lead_time_days=4, reliability_score=0.90),
        ]
        session.add_all(suppliers)
        await session.commit()
        
        # 3. Supplier Material Mappings
        # Material IDs: 1 (Wheat), 2 (Sugar), 3 (Oil), 4 (Baking Powder)
        # Supplier IDs: 1 (Agro-North), 2 (CashCarry-South), 3 (SweetLife-East), 4 (OilTech-West)
        mappings = [
            SupplierMaterial(supplier_id=1, material_id=1, unit_price=1.20, is_primary=True), # Wheat - Primary (North)
            SupplierMaterial(supplier_id=2, material_id=1, unit_price=1.50, is_primary=False), # Wheat - Backup (South - higher price)
            
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
            ProductBOM(product_name="Cream Biscuit", material_id=1, required_quantity_per_unit=0.5), # 500g wheat
            ProductBOM(product_name="Cream Biscuit", material_id=2, required_quantity_per_unit=0.2), # 200g sugar
            ProductBOM(product_name="Cream Biscuit", material_id=3, required_quantity_per_unit=0.1), # 100ml oil
            ProductBOM(product_name="Cream Biscuit", material_id=4, required_quantity_per_unit=0.01), # 10g baking powder
        ]
        session.add_all(boms)
        await session.commit()
        
        print("Data seeded successfully!")

async def main():
    await init_db()
    await seed_data()

if __name__ == "__main__":
    asyncio.run(main())
