#!/usr/bin/env python3
"""
Demonstração final do sistema camsmonteiro.ddns.net
"""

import requests
import socket
import time
import os
from datetime import datetime

def main():
    print("🎉 DEMONSTRAÇÃO FINAL - camsmonteiro.ddns.net")
    print("=" * 60)
    
    # Informações do sistema
    print("\n📋 INFORMAÇÕES DO SISTEMA:")
    print(f"   Domínio: camsmonteiro.ddns.net")
    print(f"   IP Local: 192.168.1.152")
    print(f"   IP Público: 89.114.2.135")
    print(f"   Porta: 5000")
    print(f"   Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Testar conexões
    print("\n🔍 TESTES DE CONEXÃO:")
    
    # Testar localhost
    try:
        response = requests.get('http://127.0.0.1:5000/login', timeout=5)
        print(f"   ✅ Acesso local (127.0.0.1): HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Acesso local: {e}")
    
    # Testar página de boas-vindas
    try:
        response = requests.get('http://127.0.0.1:5000/camsmonteiro', timeout=5)
        print(f"   ✅ Página de boas-vindas: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Página de boas-vindas: {e}")
    
    # Verificar gravações
    print("\n📹 SISTEMA DE GRAVAÇÕES:")
    try:
        from recording_utils import get_all_recordings
        recordings = get_all_recordings()
        
        total_videos = 0
        total_size = 0
        
        for ano, meses in recordings.items():
            for mes, dias in meses.items():
                for dia, videos in dias.items():
                    total_videos += len(videos)
                    for video in videos:
                        total_size += video.get('size', 0)
        
        print(f"   ✅ Total de vídeos: {total_videos}")
        print(f"   📁 Tamanho total: {total_size / (1024*1024):.1f} MB")
        
        # Mostrar estrutura
        print("\n   📁 Estrutura de pastas:")
        for ano, meses in list(recordings.items())[-1:]:  # Último ano
            print(f"      📂 {ano}/")
            for mes, dias in list(meses.items())[-1:]:  # Último mês
                print(f"         📂 {mes}/")
                for dia, videos in list(dias.items())[-2:]:  # Últimos 2 dias
                    print(f"            📂 {dia}/ - {len(videos)} vídeo(s)")
                    for video in videos[:2]:  # Máx 2 vídeos
                        print(f"               📹 {video['filename']}")
                    
    except Exception as e:
        print(f"   ❌ Erro ao verificar gravações: {e}")
    
    # Testar API
    print("\n🌐 API REST:")
    try:
        # Testar API de gravações
        response = requests.get('http://127.0.0.1:5000/api/recordings', timeout=5)
        if response.status_code == 200:
            print(f"   ✅ API de gravações: Disponível")
        else:
            print(f"   ⚠️  API de gravações: HTTP {response.status_code}")
        
        # Testar API de status
        response = requests.get('http://127.0.0.1:5000/api/system/status', timeout=5)
        if response.status_code == 200:
            print(f"   ✅ API de status: Disponível")
        else:
            print(f"   ⚠️  API de status: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erro na API: {e}")
    
    # URLs de acesso
    print("\n🌟 URLs DE ACESSO:")
    print("   🏠 Local:        http://127.0.0.1:5000/recordings")
    print("   🏢 Rede Local:   http://192.168.1.152:5000/recordings")
    print("   🌍 Domínio:      http://camsmonteiro.ddns.net:5000/recordings")
    print("   👋 Boas-vindas:  http://camsmonteiro.ddns.net:5000/camsmonteiro")
    
    # Funcionalidades
    print("\n✨ FUNCIONALIDADES DISPONÍVEIS:")
    print("   📹 Visualizar gravações por data")
    print("   🔍 Buscar vídeos por ano, mês ou dia")
    print("   ⬇️  Download de vídeos")
    print("   📊 Dashboard com status do sistema")
    print("   🔔 Sistema de alertas com IA")
    print("   📱 Interface responsiva para celular")
    print("   🔐 Sistema de login seguro")
    print("   ⚙️  Configurações personalizáveis")
    
    # Próximos passos
    print("\n📋 PRÓXIMOS PASSOS:")
    print("   1. Configure o redirecionamento de porta no roteador")
    print("   2. Teste o acesso externo pelo domínio")
    print("   3. Personalize as configurações conforme necessário")
    print("   4. Configure câmeras RTSP reais")
    print("   5. Ative notificações por Telegram")
    
    print("\n" + "=" * 60)
    print("🎉 SISTEMA camsmonteiro.ddns.net CONFIGURADO COM SUCESSO!")
    print("   📅 Data: " + datetime.now().strftime('%d/%m/%Y'))
    print("   ⏰ Hora: " + datetime.now().strftime('%H:%M:%S'))
    print("   🌐 Acesse: http://camsmonteiro.ddns.net:5000/recordings")
    print("=" * 60)

if __name__ == '__main__':
    main()