# app/services/assets_library.py
"""
Biblioteca de assets (áudios e imagens) mapeados por IDs.
Usado para resolver URLs a partir de IDs simples usados pela LLM.
"""
import os
from typing import Optional, Dict

# ==================== BIBLIOTECA DE ÁUDIOS ====================
AUDIO_LIBRARY: Dict[str, str] = {
    # Funil Longo - IDs principais (arquivos reais)
    "audio1_abertura_funil_longo": "funil-longo/01-boas-vindas-qualificacao.opus",
    "audio1_boas_vindas": "funil-longo/01-boas-vindas-qualificacao.opus",  # Alias principal
    "audio1_boas_vindas_file": "00000011-AUDIO-2025-11-24-22-40-30.opus",  # Arquivo real mencionado
    
    "audio2_dores_gerais": "funil-longo/02-dor-generica.opus",
    "audio2_dor_generica": "funil-longo/02-dor-generica.opus",  # Alias principal
    "audio2_dor_generica_file": "00000017-AUDIO-2025-11-24-22-47-05.opus",  # Arquivo real mencionado
    
    "audio3_explicacao_planos": "funil-longo/03-explicacao-planos.opus",
    "audio3_explicacao_planos_file": "00000032-AUDIO-2025-11-24-22-51-49.opus",  # Arquivo real mencionado
    
    "audio4_pos_compra": "funil-longo/04-recuperacao-pos-nao-compra.opus",
    "audio5_resgate_boleto": "funil-longo/04-recuperacao-pos-nao-compra.opus",  # Usa o mesmo por enquanto
    
    # Carrinho abandonado
    "audio_carrinho_abandonado": "recuperacao-50/02-audio-followup.opus",
    "audio_carrinho_abandonado_file": "00000041-AUDIO-2025-11-24-22-56-22.opus",  # Arquivo real mencionado
    
    # Aliases comuns usados no prompt
    "audio1_boas_vindas": "funil-longo/01-boas-vindas-qualificacao.opus",
    "audio1_boas_vindas_e_qualificacao": "funil-longo/01-boas-vindas-qualificacao.opus",
    "audio2_barriga_inchaco": "funil-longo/02-dor-generica.opus",  # Usa o genérico por enquanto
    "audio2_inconstancia": "funil-longo/02-dor-generica.opus",  # Usa o genérico por enquanto
    "audio2_rotina_corrida": "funil-longo/02-dor-generica.opus",  # Usa o genérico por enquanto
    "audio2_resultado_avancado": "funil-longo/02-dor-generica.opus",  # Usa o genérico por enquanto
    "audio2_compulsao_doces": "funil-longo/02-dor-generica.opus",  # Usa o genérico por enquanto
    "audio2_dor_generica": "funil-longo/02-dor-generica.opus",  # Alias mencionado no prompt
    
    # Black Friday / Mini Funil
    "audio_bf_oferta": "mini-funil-bf/01-oferta-black-friday.opus",
    "audio_bf_oferta_file": "00000047.opus",  # Arquivo real mencionado
    
    "audio_bf_follow1": "mini-funil-bf/02-followup-sem-resposta.opus",
    "audio_bf_follow1_file": "00000049.opus",  # Arquivo real mencionado
    
    "audio_bf_follow2": "recuperacao-50/02-audio-followup.opus",
    "audio_bf_follow2_file": "00000060.opus",  # Arquivo real mencionado
    
    "audio_bf_follow3": "recuperacao-50/03-audio-ultimo-chamado.opus",
    "audio_bf_follow3_file": "00000063.opus",  # Arquivo real mencionado
    
    "audio_black_friday": "mini-funil-bf/01-oferta-black-friday.opus",  # Alias usado no prompt
    "audio_recuperacao_50": "recuperacao-50/02-audio-followup.opus",  # Alias usado no prompt
    
    # Aliases usando code_name dos áudios (do audios.ts)
    "life_funil_longo_01_boas_vindas_e_qualificacao_inicial": "funil-longo/01-boas-vindas-qualificacao.opus",
    "life_funil_longo_02_dor_generica": "funil-longo/02-dor-generica.opus",
    "life_funil_longo_03_explicacao_planos": "funil-longo/03-explicacao-planos.opus",
    "life_funil_longo_04_recuperacao_pos_nao_compra": "funil-longo/04-recuperacao-pos-nao-compra.opus",
    "life_mini_funil_bf_01_oferta_black_friday": "mini-funil-bf/01-oferta-black-friday.opus",
    "life_mini_funil_bf_02_followup_sem_resposta": "mini-funil-bf/02-followup-sem-resposta.opus",
    "life_recuperacao_50_02_audio_followup": "recuperacao-50/02-audio-followup.opus",
    "life_recuperacao_50_03_audio_ultimo_chamado": "recuperacao-50/03-audio-ultimo-chamado.opus",
}

# ==================== BIBLIOTECA DE IMAGENS ====================
IMAGE_LIBRARY: Dict[str, str] = {
    # Carrossel de resultados (prova social) - Funil Longo
    "life_result_01": "00000018-PHOTO-2025-11-24-22-47-30.jpg",
    "life_result_02": "00000019-PHOTO-2025-11-24-22-47-31.jpg",
    "life_result_03": "00000020-PHOTO-2025-11-24-22-47-33.jpg",
    "life_result_04": "00000021-PHOTO-2025-11-24-22-47-34.jpg",
    "life_result_05": "00000022-PHOTO-2025-11-24-22-47-36.jpg",
    "life_result_06": "00000023-PHOTO-2025-11-24-22-47-38.jpg",
    "life_result_07": "00000024-PHOTO-2025-11-24-22-47-40.jpg",
    "life_result_08": "00000025-PHOTO-2025-11-24-22-47-43.jpg",
    
    # Black Friday / Promo
    "life_bf_01": "00000044-PHOTO-2025-11-24-22-58-54.jpg",
    "life_bf_02": "00000045-PHOTO-2025-11-24-22-59-42.jpg",
    "life_bf_03": "00000053-PHOTO-2025-11-24-23-04-16.jpg",
    
    # Imagens de campanha (mencionadas no documento)
    "img_campanha_01": "00000044-PHOTO-2025-11-24-22-58-54.jpg",
    "img_campanha_02": "00000045-PHOTO-2025-11-24-22-59-42.jpg",
    
    # Aliases para facilitar
    "prova_social_01": "00000018-PHOTO-2025-11-24-22-47-30.jpg",
    "prova_social_02": "00000019-PHOTO-2025-11-24-22-47-31.jpg",
    "prova_social_03": "00000020-PHOTO-2025-11-24-22-47-33.jpg",
    "prova_social_04": "00000021-PHOTO-2025-11-24-22-47-34.jpg",
    "prova_social_05": "00000022-PHOTO-2025-11-24-22-47-36.jpg",
    "prova_social_06": "00000023-PHOTO-2025-11-24-22-47-38.jpg",
    "prova_social_07": "00000024-PHOTO-2025-11-24-22-47-40.jpg",
    "prova_social_08": "00000025-PHOTO-2025-11-24-22-47-43.jpg",
    
    # Aliases usados no novo prompt (img_resultado_*)
    "img_resultado_01": "00000018-PHOTO-2025-11-24-22-47-30.jpg",
    "img_resultado_02": "00000019-PHOTO-2025-11-24-22-47-31.jpg",
    "img_resultado_03": "00000020-PHOTO-2025-11-24-22-47-33.jpg",
    "img_resultado_04": "00000021-PHOTO-2025-11-24-22-47-34.jpg",
    "img_resultado_05": "00000022-PHOTO-2025-11-24-22-47-36.jpg",
    "img_resultado_06": "00000023-PHOTO-2025-11-24-22-47-38.jpg",
    "img_resultado_07": "00000024-PHOTO-2025-11-24-22-47-40.jpg",
    "img_resultado_08": "00000025-PHOTO-2025-11-24-22-47-43.jpg",
    
    # Aliases para Black Friday (img_bf_*)
    "img_bf_01": "00000044-PHOTO-2025-11-24-22-58-54.jpg",
    "img_bf_02": "00000045-PHOTO-2025-11-24-22-59-42.jpg",
    "img_bf_03": "00000053-PHOTO-2025-11-24-23-04-16.jpg",
}


def resolve_audio_url(audio_id: str) -> Optional[str]:
    """
    Resolve um ID de áudio para a URL completa.
    
    Args:
        audio_id: ID do áudio (ex: "audio1_abertura_funil_longo")
        
    Returns:
        URL completa do áudio ou None se não encontrado
    """
    audio_path = AUDIO_LIBRARY.get(audio_id.strip())
    if not audio_path:
        return None
    
    # Resolve base URL
    public_base = os.getenv("PUBLIC_BASE_URL", "")
    files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
    
    if public_base and "localhost" not in public_base:
        base_url = public_base.rstrip("/")
    elif files_base and "localhost" not in files_base:
        base_url = files_base.rstrip("/")
    else:
        base_url = "http://localhost:8000"
    
    # Remove /audios/ do path se já estiver
    audio_path_clean = audio_path.lstrip("/")
    if audio_path_clean.startswith("audios/"):
        audio_path_clean = audio_path_clean[7:]  # Remove "audios/"
    
    return f"{base_url}/audios/{audio_path_clean}"


def resolve_image_url(image_id: str) -> Optional[str]:
    """
    Resolve um ID de imagem para a URL completa.
    
    Args:
        image_id: ID da imagem (ex: "life_result_01")
        
    Returns:
        URL completa da imagem ou None se não encontrado
    """
    image_filename = IMAGE_LIBRARY.get(image_id.strip())
    if not image_filename:
        return None
    
    # Resolve base URL
    public_base = os.getenv("PUBLIC_BASE_URL", "")
    files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
    
    if public_base and "localhost" not in public_base:
        base_url = public_base.rstrip("/")
    elif files_base and "localhost" not in files_base:
        base_url = files_base.rstrip("/")
    else:
        base_url = "http://localhost:8000"
    
    return f"{base_url}/images/{image_filename}"


def get_all_audio_ids() -> list[str]:
    """Retorna lista de todos os IDs de áudio disponíveis"""
    return list(AUDIO_LIBRARY.keys())


def get_all_image_ids() -> list[str]:
    """Retorna lista de todos os IDs de imagem disponíveis"""
    return list(IMAGE_LIBRARY.keys())

