#!/usr/bin/env python3
"""
Script para coletar dados do WooCommerce da Gráfica Arejano
Gera arquivo JSON com produtos, atributos e variações para uso no agente
"""

import httpx
import json
import time
from typing import Dict, List, Any
import base64

BASE_URL = "https://graficaarejano.com.br/site/wp-json/wc/v3"
CONSUMER_KEY = "ck_5944de08c0809334a4a7cdbdb66cedcd412b6759"
CONSUMER_SECRET = "cs_768734caf77b10894d05b540b3d1fbdaf04b72d9"

# Método 1: Basic Auth via Headers
auth_string = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
headers_basic = {"Authorization": f"Basic {auth_b64}"}

# Método 2: Query Parameters (alternativo)
def get(path: str, params: Dict[str, Any] = None, use_query_auth: bool = True) -> Any:
    """Faz requisição GET autenticada para a API WooCommerce"""
    url = f"{BASE_URL}{path}"
    
    # Prepara parâmetros
    request_params = params.copy() if params else {}
    
    if use_query_auth:
        # Método 2: Autenticação via query parameters
        request_params["consumer_key"] = CONSUMER_KEY
        request_params["consumer_secret"] = CONSUMER_SECRET
        headers = {}
    else:
        # Método 1: Basic Auth via headers
        headers = headers_basic
    
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, headers=headers, params=request_params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ Erro na requisição {path}: {e}")
        print(f"   Status: {e.response.status_code}")
        print(f"   Resposta: {e.response.text[:200]}")
        if not use_query_auth:
            # Tenta método alternativo
            print(f"   Tentando método alternativo (query params)...")
            return get(path, params, use_query_auth=True)
        return None
    except Exception as e:
        print(f"❌ Erro na requisição {path}: {e}")
        return None


def clean_html(text: str) -> str:
    """Remove tags HTML básicas e limpa o texto"""
    if not text:
        return ""
    import re
    # Remove tags HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Remove espaços múltiplos
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def enrich_product(product: Dict) -> Dict:
    """Enriquece produto com informações processadas"""
    # Limpa descrições HTML
    product["description_clean"] = clean_html(product.get("description", ""))
    product["short_description_clean"] = clean_html(product.get("short_description", ""))
    
    # Extrai informações de preço
    price = product.get("price", "")
    regular_price = product.get("regular_price", "")
    sale_price = product.get("sale_price", "")
    
    product["price_info"] = {
        "price": price,
        "regular_price": regular_price,
        "sale_price": sale_price,
        "on_sale": product.get("on_sale", False),
        "has_price": bool(price and price != "0")
    }
    
    # Informações de imagem principal
    images = product.get("images", [])
    product["main_image"] = images[0].get("src", "") if images else ""
    product["image_count"] = len(images)
    product["all_images"] = [img.get("src", "") for img in images[:5]]  # Primeiras 5 imagens
    
    # Categorias simplificadas
    categories = product.get("categories", [])
    product["category_names"] = [c.get("name", "") for c in categories]
    product["category_slugs"] = [c.get("slug", "") for c in categories]
    product["category_ids"] = [c.get("id", "") for c in categories]
    
    # Tags simplificadas
    tags = product.get("tags", [])
    product["tag_names"] = [t.get("name", "") for t in tags]
    product["tag_slugs"] = [t.get("slug", "") for t in tags]
    
    # Informações de estoque
    product["stock_info"] = {
        "manage_stock": product.get("manage_stock", False),
        "stock_quantity": product.get("stock_quantity"),
        "stock_status": product.get("stock_status", ""),
        "backorders": product.get("backorders", "no")
    }
    
    # Dimensões e peso (útil para cálculo de frete)
    dimensions = product.get("dimensions", {})
    product["dimensions"] = {
        "length": dimensions.get("length", ""),
        "width": dimensions.get("width", ""),
        "height": dimensions.get("height", ""),
        "unit": dimensions.get("unit", "cm")
    }
    product["weight"] = product.get("weight", "")
    product["weight_unit"] = product.get("weight_unit", "kg")
    
    # Status e visibilidade
    product["status"] = product.get("status", "publish")
    product["featured"] = product.get("featured", False)
    product["catalog_visibility"] = product.get("catalog_visibility", "visible")
    
    # SKU e código
    product["sku"] = product.get("sku", "")
    
    # Data de criação e modificação
    product["date_created"] = product.get("date_created", "")
    product["date_modified"] = product.get("date_modified", "")
    
    # Atributos do produto (para produtos variáveis)
    attributes = product.get("attributes", [])
    product["attributes_list"] = []
    for attr in attributes:
        attr_info = {
            "id": attr.get("id", ""),
            "name": attr.get("name", ""),
            "slug": attr.get("slug", ""),
            "position": attr.get("position", 0),
            "visible": attr.get("visible", False),
            "variation": attr.get("variation", False),
            "options": attr.get("options", [])
        }
        product["attributes_list"].append(attr_info)
    
    # Meta dados customizados (pode conter prazos, informações extras)
    meta_data = product.get("meta_data", [])
    product["custom_meta"] = {}
    for meta in meta_data:
        key = meta.get("key", "")
        value = meta.get("value", "")
        if key and value:
            product["custom_meta"][key] = value
    
    # Links úteis
    product["permalink"] = product.get("permalink", "")
    product["view_product_url"] = product.get("permalink", "")
    
    return product


def collect_products() -> List[Dict]:
    """Coleta todos os produtos do WooCommerce com informações enriquecidas"""
    print("📦 Coletando produtos...")
    products = []
    page = 1
    
    while True:
        # Coleta com campos adicionais
        data = get("/products", {
            "per_page": 100, 
            "page": page,
            # Garante que todos os campos sejam retornados
        })
        if not data or len(data) == 0:
            break
        
        # Enriquece cada produto
        enriched = [enrich_product(p) for p in data]
        products += enriched
        
        print(f"   Página {page}: {len(data)} produtos encontrados")
        page += 1
        time.sleep(0.2)  # Rate limiting
        
        if len(data) < 100:  # Última página
            break
    
    print(f"✅ Total de produtos: {len(products)}")
    return products


def collect_attributes() -> Dict[str, List[str]]:
    """Coleta todos os atributos e seus termos"""
    print("\n🧩 Coletando atributos...")
    attrs = get("/products/attributes")
    
    if not attrs:
        print("   Nenhum atributo encontrado")
        return {}
    
    full_attrs = {}
    for attr in attrs:
        attr_slug = attr.get('slug', '')
        attr_name = attr.get('name', '')
        print(f"   Atributo: {attr_name} ({attr_slug})")
        
        terms = get(f"/products/attributes/{attr['id']}/terms", {"per_page": 100})
        if terms:
            term_slugs = [t.get("slug", "") for t in terms]
            full_attrs[attr_slug] = {
                "name": attr_name,
                "terms": term_slugs,
                "terms_full": [{"slug": t.get("slug", ""), "name": t.get("name", "")} for t in terms]
            }
        time.sleep(0.2)
    
    print(f"✅ Total de atributos: {len(full_attrs)}")
    return full_attrs


def collect_variations(products: List[Dict]) -> Dict[str, List[Dict]]:
    """Coleta variações dos produtos variáveis com informações completas"""
    print("\n🔀 Coletando variações...")
    variations = {}
    variable_products = [p for p in products if p.get("type") == "variable"]
    
    print(f"   Produtos variáveis encontrados: {len(variable_products)}")
    
    for i, product in enumerate(variable_products):  # Coleta todos agora
        product_slug = product.get("slug", "")
        product_id = product.get("id", "")
        product_permalink = product.get("permalink", "")
        
        vars_data = get(f"/products/{product_id}/variations", {"per_page": 100})
        if vars_data:
            var_list = []
            for v in vars_data:
                var_attrs = {}
                attr_query_params = {}
                
                for attr in v.get("attributes", []):
                    attr_id = attr.get("id", "")
                    attr_name = attr.get("name", "")
                    attr_value = attr.get("option", "")
                    attr_slug = attr.get("slug", "")
                    
                    var_attrs[attr_name] = attr_value
                    
                    # Constrói parâmetros de query para o link
                    if attr_slug:
                        # Converte o valor para slug (minúsculas, hífens)
                        value_slug = attr_value.lower().replace(" ", "-").replace("(", "").replace(")", "")
                        attr_query_params[f"attribute_pa_{attr_slug.replace('pa_', '')}"] = value_slug
                
                # Constrói link direto para a variação
                link_parts = []
                for key, value in attr_query_params.items():
                    link_parts.append(f"{key}={value}")
                variation_link = f"{product_permalink}?{'&'.join(link_parts)}" if link_parts else product_permalink
                
                # Informações de preço da variação
                var_price = v.get("price", "")
                var_regular_price = v.get("regular_price", "")
                var_sale_price = v.get("sale_price", "")
                
                var_list.append({
                    "id": v.get("id", ""),
                    "sku": v.get("sku", ""),
                    "price": var_price,
                    "regular_price": var_regular_price,
                    "sale_price": var_sale_price,
                    "on_sale": v.get("on_sale", False),
                    "has_price": bool(var_price and var_price != "0"),
                    "attributes": var_attrs,
                    "link": variation_link,
                    "stock_status": v.get("stock_status", ""),
                    "manage_stock": v.get("manage_stock", False),
                    "stock_quantity": v.get("stock_quantity"),
                    "weight": v.get("weight", ""),
                    "dimensions": {
                        "length": v.get("dimensions", {}).get("length", ""),
                        "width": v.get("dimensions", {}).get("width", ""),
                        "height": v.get("dimensions", {}).get("height", ""),
                    },
                    "image": v.get("image", {}).get("src", "") if v.get("image") else "",
                })
            
            variations[product_slug] = var_list
            print(f"   [{i+1}/{len(variable_products)}] {product.get('name', '')}: {len(var_list)} variações")
        
        time.sleep(0.3)
    
    print(f"✅ Variações coletadas para {len(variations)} produtos")
    return variations


def main():
    print("🚀 Iniciando coleta de dados do WooCommerce - Gráfica Arejano\n")
    
    # Teste de conexão
    print("🔌 Testando conexão...")
    test = get("/products", {"per_page": 1})
    if not test:
        print("\n❌ Falha na conexão!")
        print("\n📋 Possíveis causas:")
        print("   1. As credenciais não têm permissão de LEITURA no WooCommerce")
        print("   2. Firewall bloqueando a rota /site/wp-json/wc/v3/*")
        print("   3. Credenciais incorretas ou expiradas")
        print("\n🔧 Como resolver:")
        print("   - No painel WooCommerce: WooCommerce > Configurações > Avançado > REST API")
        print("   - Edite a chave e verifique se tem permissão 'Read' habilitada")
        print("   - Ou crie uma nova chave com permissões de leitura")
        print("   - Verifique se o firewall permite acesso à API REST")
        return
    
    print("✅ Conexão OK!\n")
    
    # Coleta de dados
    products = collect_products()
    attributes = collect_attributes()
    variations = collect_variations(products)
    
    # Calcula estatísticas adicionais
    products_with_price = sum(1 for p in products if p.get("price_info", {}).get("has_price"))
    products_on_sale = sum(1 for p in products if p.get("price_info", {}).get("on_sale"))
    products_with_images = sum(1 for p in products if p.get("main_image"))
    products_simple = sum(1 for p in products if p.get("type") == "simple")
    products_variable = sum(1 for p in products if p.get("type") == "variable")
    products_grouped = sum(1 for p in products if p.get("type") == "grouped")
    products_external = sum(1 for p in products if p.get("type") == "external")
    
    # Conta variações totais
    total_variations = sum(len(vars_list) for vars_list in variations.values())
    
    # Estrutura final
    output = {
        "metadata": {
            "source": "WooCommerce API - Gráfica Arejano",
            "base_url": "https://graficaarejano.com.br/site",
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "2.0",  # Versão do formato de dados
            "total_products": len(products),
            "products_simple": products_simple,
            "products_variable": products_variable,
            "products_grouped": products_grouped,
            "products_external": products_external,
            "total_attributes": len(attributes),
            "total_variable_products": len(variations),
            "total_variations": total_variations,
            "products_with_price": products_with_price,
            "products_on_sale": products_on_sale,
            "products_with_images": products_with_images
        },
        "products": products,
        "attributes": attributes,
        "variations": variations
    }
    
    # Salvar arquivo
    output_file = "arejano_wc_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Dados salvos em {output_file}")
    print(f"   - {len(products)} produtos")
    print(f"   - {len(attributes)} atributos")
    print(f"   - {len(variations)} produtos com variações")


if __name__ == "__main__":
    main()

