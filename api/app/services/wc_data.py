# api/app/services/wc_data.py
"""
Módulo para consultar dados do WooCommerce do arquivo JSON
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Caminho do arquivo JSON (tenta múltiplos caminhos)
_base_path = Path(__file__).parent.parent.parent
WC_DATA_FILE = _base_path / "arejano_wc_data.json"
# Fallback: também tenta no diretório api/ e no diretório raiz do app
if not WC_DATA_FILE.exists():
    WC_DATA_FILE = _base_path / "api" / "arejano_wc_data.json"
if not WC_DATA_FILE.exists():
    # No container Docker, o arquivo está em /app/
    WC_DATA_FILE = Path("/app/arejano_wc_data.json")

# Cache do arquivo carregado
_wc_data_cache: Optional[Dict[str, Any]] = None


def _load_wc_data() -> Dict[str, Any]:
    """Carrega o arquivo JSON do WooCommerce (com cache)"""
    global _wc_data_cache
    
    if _wc_data_cache is not None:
        return _wc_data_cache
    
    if not WC_DATA_FILE.exists():
        print(f"⚠️ Arquivo não encontrado: {WC_DATA_FILE}")
        print(f"   Tentando caminhos alternativos...")
        # Tenta outros caminhos possíveis
        alt_paths = [
            Path("/app/arejano_wc_data.json"),  # Container Docker
            Path("/app/api/arejano_wc_data.json"),
            Path.cwd() / "arejano_wc_data.json",
            Path.cwd() / "api" / "arejano_wc_data.json",
            _base_path / "arejano_wc_data.json",  # Tenta novamente com base_path
        ]
        for alt_path in alt_paths:
            if alt_path.exists():
                print(f"✅ Encontrado em: {alt_path}")
                try:
                    with open(alt_path, "r", encoding="utf-8") as f:
                        _wc_data_cache = json.load(f)
                    print(f"✅ Carregado {len(_wc_data_cache.get('products', []))} produtos")
                    return _wc_data_cache
                except Exception as e:
                    print(f"❌ Erro ao carregar {alt_path}: {e}")
        
        print(f"❌ Nenhum arquivo encontrado. Retornando dados vazios.")
        return {"products": [], "attributes": {}, "variations": {}}
    
    try:
        with open(WC_DATA_FILE, "r", encoding="utf-8") as f:
            _wc_data_cache = json.load(f)
        print(f"✅ Carregado {len(_wc_data_cache.get('products', []))} produtos de {WC_DATA_FILE}")
        return _wc_data_cache
    except Exception as e:
        print(f"❌ Erro ao carregar arejano_wc_data.json: {e}")
        return {"products": [], "attributes": {}, "variations": {}}


def _normalize_text(text: str) -> str:
    """Normaliza texto para busca (remove acentos, espaços, etc.)"""
    if not text:
        return ""
    import unicodedata
    import re
    # Remove acentos
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    # Minúsculas e remove espaços extras
    text = text.lower().strip()
    # Normaliza variações comuns
    text = text.replace("pra", "para").replace("pro", "para o")
    # Remove caracteres especiais mas mantém hífens e espaços
    text = re.sub(r'[^\w\s-]', '', text)
    # Normaliza espaços múltiplos
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def lookup_product(query: str) -> Optional[Dict[str, Any]]:
    """
    Busca um produto por nome ou slug (busca flexível)
    
    Args:
        query: Nome ou slug do produto
        
    Returns:
        Dicionário com dados do produto ou None se não encontrar
    """
    data = _load_wc_data()
    products = data.get("products", [])
    
    if not products:
        return None
    
    query_normalized = _normalize_text(query)
    query_words = set(query_normalized.split())
    
    # 1. Busca exata por slug
    for product in products:
        slug = _normalize_text(product.get("slug", ""))
        if slug == query_normalized:
            return product
    
    # 2. Busca exata por nome
    for product in products:
        name = _normalize_text(product.get("name", ""))
        if name == query_normalized:
            return product
    
    # 3. Busca por palavras-chave com scoring
    best_match = None
    best_score = 0
    
    for product in products:
        name = _normalize_text(product.get("name", ""))
        slug = _normalize_text(product.get("slug", ""))
        description = _normalize_text(product.get("description_clean", ""))
        
        # Conta quantas palavras da query estão no nome/slug
        name_words = set(name.split())
        slug_words = set(slug.split())
        
        # Score baseado em palavras correspondentes
        name_matches = len(query_words & name_words)
        slug_matches = len(query_words & slug_words)
        
        # Prioriza correspondências no nome
        score = (name_matches * 3) + (slug_matches * 2)
        
        # Bônus alto se a query está contida no nome ou vice-versa
        if query_normalized in name:
            score += 20
        if name in query_normalized and len(name) > 5:
            score += 15
        if query_normalized in slug:
            score += 10
        if slug in query_normalized and len(slug) > 5:
            score += 8
        
        # Bônus se todas as palavras principais estão presentes
        if len(query_words) >= 2:
            important_words = [w for w in query_words if len(w) >= 3]
            if important_words:
                matches_in_name = sum(1 for w in important_words if w in name)
                matches_in_slug = sum(1 for w in important_words if w in slug)
                if matches_in_name == len(important_words):
                    score += 15
                elif matches_in_slug == len(important_words):
                    score += 10
        
        if score > best_score:
            best_score = score
            best_match = product
    
    # Retorna se encontrou uma correspondência razoável
    # Aceita se score >= 3 (pelo menos uma palavra importante) ou match parcial significativo
    if best_match:
        name_normalized = _normalize_text(best_match.get("name", ""))
        # Se pelo menos 50% das palavras importantes estão presentes, ou match parcial
        important_words = [w for w in query_words if len(w) >= 3]
        if important_words:
            matches = sum(1 for w in important_words if w in name_normalized)
            if matches >= len(important_words) * 0.5 or best_score >= 3:
                return best_match
        elif best_score >= 2 or query_normalized in name_normalized:
            return best_match
    
    # 4. Busca parcial mais agressiva (qualquer palavra importante)
    for product in products:
        name = _normalize_text(product.get("name", ""))
        slug = _normalize_text(product.get("slug", ""))
        
        # Verifica se palavras importantes da query estão no nome/slug
        important_words = [w for w in query_words if len(w) >= 3]
        if important_words:
            matches = sum(1 for w in important_words if w in name or w in slug)
            # Se pelo menos uma palavra importante está presente, retorna
            if matches > 0:
                return product
    
    # 5. Última tentativa: busca por substring (caso a normalização tenha removido algo importante)
    query_simple = query.lower().strip()
    for product in products:
        name_simple = product.get("name", "").lower()
        slug_simple = product.get("slug", "").lower()
        
        # Se a query está contida no nome ou vice-versa (sem normalização)
        if query_simple in name_simple or name_simple in query_simple:
            return product
        if query_simple in slug_simple or slug_simple in query_simple:
            return product
    
    return None


def search_products(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Busca produtos por nome (pode retornar múltiplos) - busca flexível
    
    Args:
        query: Termo de busca
        limit: Número máximo de resultados
        
    Returns:
        Lista de produtos encontrados (ordenados por relevância)
    """
    data = _load_wc_data()
    products = data.get("products", [])
    
    if not products:
        return []
    
    query_normalized = _normalize_text(query)
    query_words = set(query_normalized.split())
    results_with_score = []
    
    for product in products:
        name = _normalize_text(product.get("name", ""))
        slug = _normalize_text(product.get("slug", ""))
        description = _normalize_text(product.get("description_clean", ""))
        
        # Calcula score de relevância
        score = 0
        
        # Match exato no nome
        if query_normalized == name:
            score += 100
        # Match exato no slug
        elif query_normalized == slug:
            score += 90
        # Query contida no nome
        elif query_normalized in name:
            score += 50
        # Query contida no slug
        elif query_normalized in slug:
            score += 40
        # Nome contido na query
        elif name in query_normalized and len(name) > 3:
            score += 30
        
        # Conta palavras correspondentes
        name_words = set(name.split())
        slug_words = set(slug.split())
        name_matches = len(query_words & name_words)
        slug_matches = len(query_words & slug_words)
        score += (name_matches * 5) + (slug_matches * 3)
        
        # Match na descrição (menor peso)
        if query_normalized in description:
            score += 10
        
        # Match parcial de palavras
        for word in query_words:
            if len(word) >= 3:
                if word in name:
                    score += 2
                if word in slug:
                    score += 1
        
        if score > 0:
            results_with_score.append((score, product))
    
    # Ordena por score (maior primeiro) e retorna
    results_with_score.sort(key=lambda x: x[0], reverse=True)
    return [product for _, product in results_with_score[:limit]]


def _format_price(price_value: Any) -> Optional[str]:
    """
    Formata um valor de preço para string com formatação brasileira
    """
    if price_value is None or price_value == "" or price_value == "0":
        return None
    
    try:
        # Tenta converter para float
        if isinstance(price_value, str):
            # Remove caracteres não numéricos exceto vírgula e ponto
            price_str = price_value.replace("R$", "").replace(" ", "").strip()
            # Substitui vírgula por ponto para conversão
            price_str = price_str.replace(",", ".")
            price_float = float(price_str)
        else:
            price_float = float(price_value)
        
        if price_float <= 0:
            return None
        
        # Formata como moeda brasileira
        return f"R$ {price_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return None


def get_product_price(product_slug: str, attributes: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Obtém preço de um produto, considerando variações se for produto variável
    
    Args:
        product_slug: Slug do produto
        attributes: Dicionário com atributos (ex: {"pa_tamanho": "90x50mm", "pa_quantidade": "1000"})
        
    Returns:
        Dicionário com informações de preço ou None se produto não existir
    """
    product = lookup_product(product_slug)
    if not product:
        return {
            "error": "Produto não encontrado",
            "message": f"O produto '{product_slug}' não foi encontrado no catálogo. Verifique se o slug está correto ou use 'lookup_product' ou 'search_products' para encontrar produtos disponíveis.",
            "product_slug": product_slug
        }
    
    # Produto simples
    if product.get("type") == "simple":
        price_info = product.get("price_info", {})
        
        # Obtém preços brutos
        raw_price = price_info.get("price") or product.get("price", "")
        raw_regular_price = price_info.get("regular_price") or product.get("regular_price", "")
        raw_sale_price = price_info.get("sale_price") or product.get("sale_price", "")
        
        # Prioriza sale_price se estiver em promoção, senão usa regular_price ou price
        if price_info.get("on_sale", False) and raw_sale_price:
            final_price = raw_sale_price
        elif raw_regular_price:
            final_price = raw_regular_price
        else:
            final_price = raw_price
        
        price_formatted = _format_price(final_price)
        
        return {
            "product_name": product.get("name"),
            "product_slug": product.get("slug"),
            "type": "simple",
            "price": price_formatted,
            "price_raw": final_price,
            "regular_price": _format_price(raw_regular_price) if raw_regular_price else None,
            "sale_price": _format_price(raw_sale_price) if raw_sale_price else None,
            "on_sale": price_info.get("on_sale", False),
            "link": product.get("permalink", ""),
            "has_price": bool(price_formatted)
        }
    
    # Produto variável - busca variação correspondente
    if product.get("type") == "variable" and attributes:
        data = _load_wc_data()
        variations = data.get("variations", {}).get(product_slug, [])
        
        # Normaliza os atributos recebidos para comparação
        normalized_attrs = {}
        for attr_name, attr_value in attributes.items():
            # Remove prefixos comuns
            clean_key = attr_name.replace("pa_", "").replace("attribute_pa_", "")
            normalized_attrs[clean_key] = attr_value.lower().strip()
        
        # Tenta encontrar variação que corresponda aos atributos
        best_match = None
        best_match_score = 0
        
        for variation in variations:
            var_attrs = variation.get("attributes", {})
            match_count = 0
            total_attrs = len(normalized_attrs)
            
            # Normaliza atributos da variação
            normalized_var_attrs = {}
            for var_attr_key, var_attr_value in var_attrs.items():
                clean_key = var_attr_key.replace("pa_", "").replace("attribute_pa_", "")
                if var_attr_value:
                    normalized_var_attrs[clean_key] = str(var_attr_value).lower().strip()
            
            # Conta quantos atributos correspondem
            for attr_key, attr_value in normalized_attrs.items():
                var_value = normalized_var_attrs.get(attr_key)
                if var_value and var_value == attr_value:
                    match_count += 1
            
            # Se todos os atributos correspondem, é match perfeito
            if match_count == total_attrs and total_attrs > 0:
                best_match = variation
                break
            elif match_count > best_match_score:
                best_match_score = match_count
                best_match = variation
        
        if best_match:
            raw_price = best_match.get("price", "")
            raw_regular_price = best_match.get("regular_price", "")
            raw_sale_price = best_match.get("sale_price", "")
            
            # Prioriza sale_price se estiver em promoção
            if best_match.get("on_sale", False) and raw_sale_price:
                final_price = raw_sale_price
            elif raw_regular_price:
                final_price = raw_regular_price
            else:
                final_price = raw_price
            
            price_formatted = _format_price(final_price)
            
            return {
                "product_name": product.get("name"),
                "product_slug": product.get("slug"),
                "type": "variation",
                "variation_id": best_match.get("id"),
                "price": price_formatted,
                "price_raw": final_price,
                "regular_price": _format_price(raw_regular_price) if raw_regular_price else None,
                "sale_price": _format_price(raw_sale_price) if raw_sale_price else None,
                "on_sale": best_match.get("on_sale", False),
                "link": best_match.get("link", product.get("permalink", "")),
                "attributes": best_match.get("attributes", {}),
                "has_price": bool(price_formatted)
            }
        
        # Se não encontrou variação exata, retorna aviso
        return {
            "product_name": product.get("name"),
            "product_slug": product.get("slug"),
            "type": "variable",
            "error": "Variação não encontrada",
            "message": f"A combinação de atributos especificada não foi encontrada para este produto. Use 'get_product_attributes' para ver quais atributos e valores são válidos antes de informar o preço.",
            "attributes_requested": attributes,
            "link": product.get("permalink", ""),
            "note": "Este produto tem variações. O preço depende dos atributos selecionados. Verifique os atributos disponíveis antes de informar o preço. NÃO invente preços."
        }
    
    # Produto variável sem atributos - não pode dar preço exato
    return {
        "product_name": product.get("name"),
        "product_slug": product.get("slug"),
        "type": "variable",
        "error": "Atributos necessários",
        "message": "Este produto tem variações e requer atributos para calcular o preço. Use 'get_product_attributes' para ver quais atributos são necessários antes de informar o preço.",
        "link": product.get("permalink", ""),
        "note": "Este produto tem variações. O preço depende dos atributos selecionados. NÃO é possível informar o preço sem os atributos específicos. NÃO invente preços."
    }


def get_product_attributes(product_slug: str, selected_attributes: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Obtém atributos disponíveis para um produto, filtrando opções baseado em atributos já selecionados
    
    Args:
        product_slug: Slug do produto
        selected_attributes: Dicionário com atributos já selecionados (ex: {"pa_tamanho": "200x90mm"})
                            Quando fornecido, retorna apenas as opções válidas para os atributos restantes
        
    Returns:
        Dicionário com atributos e suas opções ou None
    """
    product = lookup_product(product_slug)
    if not product:
        return None
    
    attributes = product.get("attributes", [])
    if not attributes:
        return {"product_slug": product_slug, "attributes": []}
    
    result = {
        "product_slug": product_slug,
        "product_name": product.get("name"),
        "attributes": []
    }
    
    # Se tem atributos selecionados, filtra opções baseado nas variações válidas
    if selected_attributes and product.get("type") == "variable":
        data = _load_wc_data()
        variations = data.get("variations", {}).get(product_slug, [])
        
        # Normaliza atributos selecionados
        normalized_selected = {}
        for attr_name, attr_value in selected_attributes.items():
            clean_key = attr_name.replace("pa_", "").replace("attribute_pa_", "")
            normalized_selected[clean_key] = str(attr_value).lower().strip()
        
        # Encontra variações que correspondem aos atributos selecionados
        matching_variations = []
        for variation in variations:
            var_attrs = variation.get("attributes", {})
            matches = True
            
            for selected_key, selected_value in normalized_selected.items():
                var_value = var_attrs.get(f"pa_{selected_key}") or var_attrs.get(f"attribute_pa_{selected_key}")
                if var_value:
                    var_value_normalized = str(var_value).lower().strip()
                    if var_value_normalized != selected_value:
                        matches = False
                        break
                else:
                    matches = False
                    break
            
            if matches:
                matching_variations.append(variation)
        
        # Para cada atributo, coleta apenas as opções que existem nas variações correspondentes
        for attr in attributes:
            attr_slug = attr.get("slug", "")
            attr_name = attr.get("name", "")
            
            # Se este atributo já foi selecionado, mostra apenas o valor selecionado
            clean_attr_key = attr_slug.replace("pa_", "")
            if clean_attr_key in normalized_selected:
                selected_value = normalized_selected[clean_attr_key]
                # Encontra o valor original (não normalizado) nas opções
                matching_option = None
                for option in attr.get("options", []):
                    if str(option).lower().strip() == selected_value:
                        matching_option = option
                        break
                
                # Se não encontrou match exato, tenta match parcial (para casos como "200x90mm" vs "200 x 90 mm")
                if not matching_option:
                    for option in attr.get("options", []):
                        option_normalized = str(option).lower().strip().replace(" ", "").replace("x", "x")
                        if option_normalized == selected_value.replace(" ", "").replace("x", "x"):
                            matching_option = option
                            break
                
                result["attributes"].append({
                    "id": attr.get("id"),
                    "name": attr_name,
                    "slug": attr_slug,
                    "options": [matching_option] if matching_option else [selected_value],
                    "selected": selected_value
                })
            else:
                # Coleta opções válidas para este atributo nas variações correspondentes
                valid_options = set()
                for variation in matching_variations:
                    var_attrs = variation.get("attributes", {})
                    var_value = var_attrs.get(attr_slug) or var_attrs.get(f"attribute_{attr_slug}")
                    if var_value:
                        valid_options.add(str(var_value))
                
                # Filtra opções originais para manter apenas as válidas
                original_options = attr.get("options", [])
                filtered_options = [opt for opt in original_options if str(opt) in valid_options or not valid_options]
                
                # Se não encontrou variações correspondentes, mostra todas as opções
                if not matching_variations:
                    filtered_options = original_options
                
                result["attributes"].append({
                    "id": attr.get("id"),
                    "name": attr_name,
                    "slug": attr_slug,
                    "options": filtered_options if filtered_options else original_options
                })
    else:
        # Sem filtro, retorna todas as opções
        for attr in attributes:
            result["attributes"].append({
                "id": attr.get("id"),
                "name": attr.get("name"),
                "slug": attr.get("slug"),
                "options": attr.get("options", [])
            })
    
    return result


def get_product_variations(product_slug: str) -> List[Dict[str, Any]]:
    """
    Obtém todas as variações de um produto variável
    
    Args:
        product_slug: Slug do produto
        
    Returns:
        Lista de variações
    """
    data = _load_wc_data()
    variations = data.get("variations", {}).get(product_slug, [])
    
    # Retorna apenas informações essenciais
    return [
        {
            "id": v.get("id"),
            "price": v.get("price"),
            "regular_price": v.get("regular_price"),
            "sale_price": v.get("sale_price"),
            "on_sale": v.get("on_sale", False),
            "attributes": v.get("attributes", {}),
            "link": v.get("link", "")
        }
        for v in variations
    ]


def get_product_description(product_slug: str) -> Optional[Dict[str, Any]]:
    """
    Obtém descrição de um produto
    
    Args:
        product_slug: Slug do produto
        
    Returns:
        Dicionário com descrições ou None
    """
    product = lookup_product(product_slug)
    if not product:
        return None
    
    return {
        "product_name": product.get("name"),
        "product_slug": product.get("slug"),
        "description": product.get("description_clean", ""),
        "short_description": product.get("short_description_clean", ""),
        "link": product.get("permalink", "")
    }


def build_product_link(product_slug: str, attributes: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Constrói link completo para um produto com atributos, validando combinações nas variações
    
    Args:
        product_slug: Slug do produto
        attributes: Dicionário com atributos (ex: {"pa_tamanho": "90x50mm", "pa_quantidade": "1000"})
        
    Returns:
        Dicionário com link, se encontrou variação válida, e informações sobre a combinação
    """
    product = lookup_product(product_slug)
    if not product:
        return {
            "error": "Produto não encontrado",
            "message": f"O produto '{product_slug}' não foi encontrado no catálogo."
        }
    
    base_url = product.get("permalink", "")
    
    # Se não tem atributos, retorna link base
    if not attributes:
        return {
            "link": base_url,
            "type": "base",
            "message": "Link base do produto (sem atributos selecionados)"
        }
    
    # Se for produto variável, busca variação correspondente
    if product.get("type") == "variable":
        data = _load_wc_data()
        variations = data.get("variations", {}).get(product_slug, [])
        
        if not variations:
            # Se não tem variações, constrói link manualmente
            return _build_link_manually(base_url, attributes)
        
        # Normaliza os atributos recebidos para comparação
        normalized_attrs = {}
        for attr_name, attr_value in attributes.items():
            # Remove prefixos comuns
            clean_key = attr_name.replace("pa_", "").replace("attribute_pa_", "")
            normalized_attrs[clean_key] = attr_value.lower().strip()
        
        # Tenta encontrar variação que corresponda aos atributos
        best_match = None
        best_match_score = 0
        
        for variation in variations:
            var_attrs = variation.get("attributes", {})
            match_count = 0
            total_attrs = len(normalized_attrs)
            
            # Normaliza atributos da variação
            normalized_var_attrs = {}
            for var_attr_key, var_attr_value in var_attrs.items():
                clean_key = var_attr_key.replace("pa_", "").replace("attribute_pa_", "")
                if var_attr_value:
                    normalized_var_attrs[clean_key] = str(var_attr_value).lower().strip()
            
            # Conta quantos atributos correspondem
            for attr_key, attr_value in normalized_attrs.items():
                var_value = normalized_var_attrs.get(attr_key)
                if var_value and var_value == attr_value:
                    match_count += 1
            
            # Se todos os atributos correspondem, é match perfeito
            if match_count == total_attrs and total_attrs > 0:
                best_match = variation
                break
            elif match_count > best_match_score:
                best_match_score = match_count
                best_match = variation
        
        if best_match:
            # Usa o link da variação (já está correto no JSON)
            variation_link = best_match.get("link", "")
            if variation_link:
                return {
                    "link": variation_link,
                    "type": "variation",
                    "variation_id": best_match.get("id"),
                    "match_score": best_match_score,
                    "total_attrs": len(normalized_attrs),
                    "attributes": best_match.get("attributes", {}),
                    "message": "Link gerado com base na variação encontrada"
                }
            else:
                # Se não tem link na variação, constrói manualmente
                return _build_link_manually(base_url, best_match.get("attributes", {}))
        
        # Se não encontrou variação, tenta construir link manualmente
        return _build_link_manually(base_url, attributes)
    
    # Produto simples - constrói link manualmente
    return _build_link_manually(base_url, attributes)


def _build_link_manually(base_url: str, attributes: Dict[str, str]) -> Dict[str, Any]:
    """
    Constrói link manualmente quando não encontra variação exata
    Tenta validar usando get_product_attributes se possível
    """
    if not attributes:
        return {
            "link": base_url,
            "type": "base",
            "message": "Link base (sem atributos)"
        }
    
    # Tenta validar atributos usando get_product_attributes
    # (isso será feito pela IA antes de chamar build_product_link)
    
    query_parts = []
    for attr_name, attr_value in attributes.items():
        # Normaliza nome do atributo
        if not attr_name.startswith("attribute_pa_"):
            if attr_name.startswith("pa_"):
                attr_name = f"attribute_{attr_name}"
            else:
                attr_name = f"attribute_pa_{attr_name}"
        
        # Converte valor para slug (minúsculas, hífens)
        # Remove espaços, parênteses, pontos, e normaliza
        value_slug = str(attr_value).lower().strip()
        value_slug = value_slug.replace(" ", "-")
        value_slug = value_slug.replace("(", "").replace(")", "")
        value_slug = value_slug.replace(".", "")
        value_slug = value_slug.replace("x", "x")  # Mantém 'x' para dimensões como 40x40mm
        # Remove múltiplos hífens consecutivos
        while "--" in value_slug:
            value_slug = value_slug.replace("--", "-")
        # Remove hífen no final se houver
        value_slug = value_slug.rstrip("-")
        
        query_parts.append(f"{attr_name}={value_slug}")
    
    if query_parts:
        link = f"{base_url}?{'&'.join(query_parts)}"
        return {
            "link": link,
            "type": "manual",
            "message": "Link construído manualmente (combinação pode não ser válida)",
            "warning": "Esta combinação de atributos pode não existir. Verifique no site ou use 'get_product_attributes' para confirmar os valores válidos."
        }
    
    return {
        "link": base_url,
        "type": "base",
        "message": "Link base"
    }

