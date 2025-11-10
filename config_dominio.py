#!/usr/bin/env python3
"""
Configuração específica para o domínio camsmonteiro.ddns.net
"""

import os
from config import *

# Configurações do domínio
DOMINIO_CONFIG = {
    'server_name': 'camsmonteiro.ddns.net:5000',
    'host': '0.0.0.0',
    'port': 5000,
    'debug': False,
    'use_reloader': False
}

# Configurações de segurança para acesso externo
SECURITY.update({
    'session_cookie_secure': True,
    'session_cookie_http_only': True,
    'session_cookie_samesite': 'Lax',
    'permanent_session_lifetime': 3600  # 1 hora
})

# Adicionar domínio à whitelist
IP_WHITELIST.extend([
    'camsmonteiro.ddns.net',
    'localhost',
    '127.0.0.1',
    '192.168.1.152'  # IP local
])

print("=== CONFIGURAÇÃO PARA camsmonteiro.ddns.net ===")
print(f"Domínio: {DOMINIO_CONFIG['server_name']}")
print(f"Host: {DOMINIO_CONFIG['host']}")
print(f"Porta: {DOMINIO_CONFIG['port']}")
print("")
print("URLs de acesso:")
print(f"- Sistema de gravações: http://camsmonteiro.ddns.net:5000/recordings")
print(f"- Login: http://camsmonteiro.ddns.net:5000/login")
print(f"- Dashboard: http://camsmonteiro.ddns.net:5000/")
print("")
print("⚠️  IMPORTANTE:")
print("1. Libere a porta 5000 no firewall do Windows")
print("2. Configure o redirecionamento de porta no roteador")
print("3. Verifique se o DDNS está atualizado com seu IP atual")