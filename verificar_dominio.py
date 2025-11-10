#!/usr/bin/env python3
"""
Verificação completa do sistema para o domínio camsmonteiro.ddns.net
"""

import requests
import socket
import subprocess
import time
import os

def verificar_porta():
    """Verificar se a porta 5000 está acessível"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 5000))
        sock.close()
        return result == 0
    except:
        return False

def verificar_servidor():
    """Verificar se o servidor está respondendo"""
    try:
        response = requests.get('http://127.0.0.1:5000/login', timeout=10)
        return response.status_code == 200
    except:
        return False

def obter_ip_publico():
    """Obter IP público atual"""
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text.strip()
    except:
        return None

def verificar_firewall():
    """Verificar regras do firewall"""
    try:
        result = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'], 
                              capture_output=True, text=True)
        return '5000' in result.stdout or '5000' in result.stderr
    except:
        return False

def main():
    print("🔍 VERIFICAÇÃO DO SISTEMA camsmonteiro.ddns.net")
    print("=" * 50)
    
    # Verificar se servidor está rodando
    print("\n📡 Verificando servidor...")
    if verificar_porta():
        print("✅ Porta 5000 está aberta")
        if verificar_servidor():
            print("✅ Servidor Flask está respondendo")
        else:
            print("❌ Servidor Flask não está respondendo")
    else:
        print("❌ Porta 5000 está fechada - servidor não está rodando")
    
    # Informações de rede
    print("\n🌐 Informações de rede:")
    hostname = socket.gethostname()
    ip_local = socket.gethostbyname(hostname)
    print(f"  Hostname: {hostname}")
    print(f"  IP Local: {ip_local}")
    
    ip_publico = obter_ip_publico()
    if ip_publico:
        print(f"  IP Público: {ip_publico}")
    
    # Verificar firewall
    print("\n🔒 Verificando firewall:")
    if verificar_firewall():
        print("⚠️  Firewall detectado - verifique se a porta 5000 está liberada")
    else:
        print("ℹ️  Nenhuma regra específica encontrada no firewall")
    
    # URLs de acesso
    print("\n🌟 URLs de acesso:")
    print(f"  Local: http://127.0.0.1:5000/recordings")
    print(f"  Rede Local: http://{ip_local}:5000/recordings")
    if ip_publico:
        print(f"  Domínio: http://camsmonteiro.ddns.net:5000/recordings")
    
    # Testar gravações
    print("\n📹 Verificando sistema de gravações:")
    try:
        from recording_utils import get_all_recordings
        recordings = get_all_recordings()
        total_videos = 0
        for ano, meses in recordings.items():
            for mes, dias in meses.items():
                for dia, videos in dias.items():
                    total_videos += len(videos)
        
        print(f"✅ Sistema de gravações OK - {total_videos} vídeos encontrados")
        
        # Listar gravações recentes
        print("\n📁 Gravações encontradas:")
        for ano, meses in list(recordings.items())[-1:]:  # Último ano
            for mes, dias in list(meses.items())[-1:]:  # Último mês
                for dia, videos in list(dias.items())[-2:]:  # Últimos 2 dias
                    print(f"  {ano}/{mes}/{dia}: {len(videos)} vídeos")
                    for video in videos[:3]:  # Máx 3 vídeos por dia
                        print(f"    - {video['filename']} ({video['size_formatted']})")
                    
    except Exception as e:
        print(f"❌ Erro no sistema de gravações: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Verificação concluída!")
    print("\n📝 PRÓXIMOS PASSOS:")
    print("1. Libere a porta 5000 no firewall do Windows")
    print("2. Configure o redirecionamento de porta no seu roteador")
    print("3. Teste o acesso externo: http://camsmonteiro.ddns.net:5000/recordings")

if __name__ == '__main__':
    main()