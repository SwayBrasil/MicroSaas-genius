"""
Script para sincronizar produtos da Eduzz manualmente.
Lista de produtos fornecida pelo usuário.
"""
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db import SessionLocal
from app.models import ProductExternal

# Lista de produtos da Eduzz fornecida pelo usuário
EDUZZ_PRODUCTS = [
    {"id": "2382728", "title": "ACESSO MENSAL - LIFE MÉTODO PLM - 0404"},
    {"id": "2382997", "title": "ACESSO MENSAL - LIFE MÉTODO PLM - 1102"},
    {"id": "2352153", "title": "ACESSO MENSAL - LIFE MÉTODO PLM 01"},
    {"id": "2455207", "title": "CARTÃO DE VISITAS TECNOLÓGICO."},
    {"id": "2109729", "title": "DESAFIO 28 DIAS PALOMA MORAES"},
    {"id": "2180340", "title": "DESAFIO 28 DIAS PALOMA MORAES - DEZEMBRO 2023"},
    {"id": "2108559", "title": "DESAFIO 28 DIAS PALOMA MORAES - OFERTA EXCLUSIVA"},
    {"id": "2184785", "title": "Desafio Completo de 28 Dias Com Paloma Moraes - Edição Dezembro 2023"},
    {"id": "2562423", "title": "LIFE ACESSO ANUAL - 2 ANOS"},
    {"id": "2562393", "title": "LIFE ACESSO MENSAL"},
    {"id": "2571885", "title": "LIFE VITALÍCIO - 2025"},
    {"id": "2681898", "title": "LIFE VITALÍCIO - 2025x"},
    {"id": "2455378", "title": "MENTORIA EXCLUSIVA"},
    {"id": "2459386", "title": "MENTORIA EXCLUSIVA + 9 MESES"},
    {"id": "2124224", "title": "OFERTA RELÂMPAGO - DESAFIO 28 DIAS PALOMA MORAES"},
    {"id": "2457307", "title": "ACESSO MENSAL - LIFE 2025"},  # Já conhecido
]

def sync_eduzz_products():
    """Sincroniza produtos da Eduzz no banco de dados."""
    db = SessionLocal()
    created_count = 0
    updated_count = 0
    
    try:
        for product_data in EDUZZ_PRODUCTS:
            product_id = product_data["id"]
            title = product_data["title"]
            
            # Verifica se já existe
            existing = db.query(ProductExternal).filter(
                ProductExternal.external_product_id == product_id,
                ProductExternal.source == "eduzz"
            ).first()
            
            if existing:
                # Atualiza se o título mudou
                if existing.title != title:
                    existing.title = title
                    updated_count += 1
                    print(f"✅ Atualizado: {product_id} - {title}")
                else:
                    print(f"⏭️  Já existe: {product_id} - {title}")
            else:
                # Cria novo
                new_product = ProductExternal(
                    external_product_id=product_id,
                    title=title,
                    status="active",
                    source="eduzz",
                    raw_data={"product_id": product_id, "title": title},
                )
                db.add(new_product)
                created_count += 1
                print(f"➕ Criado: {product_id} - {title}")
        
        db.commit()
        print(f"\n✅ Sincronização concluída!")
        print(f"   ➕ Criados: {created_count}")
        print(f"   🔄 Atualizados: {updated_count}")
        print(f"   📦 Total: {len(EDUZZ_PRODUCTS)}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao sincronizar: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    sync_eduzz_products()


