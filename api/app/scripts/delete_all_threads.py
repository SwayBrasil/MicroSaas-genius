#!/usr/bin/env python3
"""
Script para apagar TODAS as threads, mensagens e contatos do banco de dados.
⚠️ ATENÇÃO: Esta operação é IRREVERSÍVEL!

Uso: python delete_all_threads.py
"""
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db import SessionLocal
from app.models import Thread, Message, Contact, ContactTag, ContactNote, ContactReminder, SaleEvent, CartEvent, SubscriptionExternal


def delete_all_threads():
    """
    Apaga TODAS as threads, mensagens e contatos do banco de dados.
    """
    db = SessionLocal()
    
    try:
        # Conta antes de apagar
        total_threads = db.query(Thread).count()
        total_messages = db.query(Message).count()
        total_contacts = db.query(Contact).count()
        
        print(f"📊 Estatísticas antes da exclusão:")
        print(f"   💬 Threads: {total_threads}")
        print(f"   📨 Mensagens: {total_messages}")
        print(f"   👤 Contatos: {total_contacts}")
        
        if total_threads == 0:
            print("\n✅ Nenhuma thread encontrada. Nada para apagar.")
            return
        
        print(f"\n🗑️  Iniciando exclusão...")
        
        # Apaga mensagens primeiro (devido a foreign keys)
        deleted_messages = db.query(Message).delete()
        print(f"   ✅ {deleted_messages} mensagem(ns) apagada(s)")
        
        # Apaga eventos de vendas e carrinho antes dos contatos
        deleted_sales_events = db.query(SaleEvent).delete()
        print(f"   ✅ {deleted_sales_events} evento(s) de venda apagado(s)")
        
        deleted_cart_events = db.query(CartEvent).delete()
        print(f"   ✅ {deleted_cart_events} evento(s) de carrinho apagado(s)")
        
        # Apaga subscriptions antes dos contatos
        deleted_subscriptions = db.query(SubscriptionExternal).delete()
        print(f"   ✅ {deleted_subscriptions} subscription(s) apagada(s)")
        
        # Apaga contatos e seus relacionamentos (tags, notes, reminders)
        # O cascade vai apagar automaticamente os relacionamentos
        deleted_contacts = db.query(Contact).delete()
        print(f"   ✅ {deleted_contacts} contato(s) apagado(s)")
        
        # Apaga threads
        deleted_threads = db.query(Thread).delete()
        print(f"   ✅ {deleted_threads} thread(s) apagada(s)")
        
        db.commit()
        
        print(f"\n🎉 Concluído!")
        print(f"   📊 Total de threads apagadas: {deleted_threads}")
        print(f"   📊 Total de mensagens apagadas: {deleted_messages}")
        print(f"   📊 Total de contatos apagados: {deleted_contacts}")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao apagar threads: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("⚠️  ATENÇÃO: Esta operação vai apagar TODAS as threads, mensagens e contatos!")
    print("⚠️  Esta operação é IRREVERSÍVEL!")
    
    # Permite pular confirmação com --yes
    if "--yes" not in sys.argv:
        try:
            confirm = input("\n⚠️  Tem certeza absoluta? Digite 'APAGAR TUDO' para confirmar: ")
            if confirm != "APAGAR TUDO":
                print("❌ Operação cancelada.")
                sys.exit(0)
        except EOFError:
            print("\n❌ Não é possível ler input interativo. Use --yes para confirmar automaticamente.")
            print("   Exemplo: python delete_all_threads.py --yes")
            sys.exit(1)
    else:
        print("\n✅ Modo --yes ativado. Prosseguindo com exclusão...")
    
    delete_all_threads()

