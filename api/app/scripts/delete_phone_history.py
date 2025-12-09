#!/usr/bin/env python3
"""
Script para apagar histórico de mensagens de um número específico.
Uso: python delete_phone_history.py +556183364337
"""
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db import SessionLocal
from app.models import Thread, Message, Contact
from sqlalchemy import or_


def normalize_phone(phone: str) -> str:
    """Normaliza número de telefone para formato E.164 consistente."""
    if not phone:
        return ""
    # Remove 'whatsapp:' prefix
    normalized = str(phone).replace("whatsapp:", "").strip()
    # Remove espaços e caracteres especiais (exceto +)
    normalized = normalized.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    # Garante que comece com +
    if normalized and not normalized.startswith("+"):
        normalized = "+" + normalized
    return normalized


def delete_phone_history(phone: str, delete_threads: bool = True):
    """
    Apaga histórico de mensagens de um número específico.
    
    Args:
        phone: Número no formato E.164 (ex: +556183364337)
        delete_threads: Se True, apaga as threads também. Se False, apenas apaga mensagens.
    """
    db = SessionLocal()
    
    try:
        # Normaliza o número
        normalized_phone = normalize_phone(phone)
        print(f"🔍 Buscando threads para número: {normalized_phone}")
        
        # Busca todas as threads com esse número (normalizando os números do banco também)
        all_threads = db.query(Thread).filter(Thread.external_user_phone.isnot(None)).all()
        matching_threads = []
        
        for thread in all_threads:
            if thread.external_user_phone:
                normalized_db_phone = normalize_phone(thread.external_user_phone)
                if normalized_db_phone == normalized_phone:
                    matching_threads.append(thread)
        
        if not matching_threads:
            print(f"❌ Nenhuma thread encontrada para o número {normalized_phone}")
            return
        
        print(f"✅ Encontradas {len(matching_threads)} thread(s) para o número {normalized_phone}")
        
        total_messages = 0
        total_contacts = 0
        
        for thread in matching_threads:
            print(f"\n📋 Processando thread ID={thread.id} (título: {thread.title})")
            
            # Conta mensagens
            message_count = db.query(Message).filter(Message.thread_id == thread.id).count()
            print(f"   💬 {message_count} mensagem(ns) encontrada(s)")
            
            # Apaga mensagens
            deleted_messages = db.query(Message).filter(Message.thread_id == thread.id).delete()
            total_messages += deleted_messages
            print(f"   ✅ {deleted_messages} mensagem(ns) apagada(s)")
            
            # Verifica se há contato associado
            contact = db.query(Contact).filter(Contact.thread_id == thread.id).first()
            if contact:
                print(f"   👤 Contato encontrado (ID={contact.id}, nome={contact.name})")
                if delete_threads:
                    # Apaga contato também (cascade vai apagar tags, notes, reminders)
                    db.delete(contact)
                    total_contacts += 1
                    print(f"   ✅ Contato apagado")
            
            # Apaga thread se solicitado
            if delete_threads:
                db.delete(thread)
                print(f"   ✅ Thread apagada")
        
        db.commit()
        
        print(f"\n🎉 Concluído!")
        print(f"   📊 Total de mensagens apagadas: {total_messages}")
        if delete_threads:
            print(f"   📊 Total de threads apagadas: {len(matching_threads)}")
            print(f"   📊 Total de contatos apagados: {total_contacts}")
        else:
            print(f"   ℹ️  Threads mantidas (apenas mensagens foram apagadas)")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao apagar histórico: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python delete_phone_history.py <número> [--keep-threads]")
        print("Exemplo: python delete_phone_history.py +556183364337")
        print("Exemplo: python delete_phone_history.py +556183364337 --keep-threads")
        sys.exit(1)
    
    phone = sys.argv[1]
    delete_threads = "--keep-threads" not in sys.argv
    
    if not delete_threads:
        print("⚠️  Modo: manter threads (apenas mensagens serão apagadas)")
    else:
        print("⚠️  Modo: apagar tudo (mensagens, threads e contatos)")
    
    confirm = input(f"\n⚠️  Tem certeza que deseja apagar o histórico de {phone}? (digite 'sim' para confirmar): ")
    if confirm.lower() != "sim":
        print("❌ Operação cancelada.")
        sys.exit(0)
    
    delete_phone_history(phone, delete_threads=delete_threads)

