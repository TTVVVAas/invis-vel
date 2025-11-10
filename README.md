# 🎥 Sistema de Vigilância IA com RTSP

Sistema completo de vigilância com inteligência artificial para detecção de pessoas, acessível via web com autenticação.

## ✨ Funcionalidades

- 📹 **Acesso RTSP** às câmeras IP
- 🎯 **Detecção de movimento** com OpenCV MOG2
- 🧠 **Detecção de pessoas** com YOLOv8
- 🔐 **Sistema de login** com Flask-Login
- 🌐 **Interface web** responsiva e moderna
- 📱 **Acesso remoto** via internet (com port forwarding)
- 🚨 **Alertas visuais** e salvamento de imagens
- 📊 **Estatísticas em tempo real**
- ⚙️ **Configuração fácil** via interface web

## 🚀 Instalação Rápida

### 1. Clone ou baixe o projeto
```bash
cd meu_site_ai_rtsp
```

### 2. Crie ambiente virtual (recomendado)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure a câmera RTSP
Edite o arquivo `config.py` e ajuste:
```python
CAMERA = {
    'rtsp_url': 'rtsp://usuario:senha@ip_da_camera:554/stream',
    # ... outras configurações
}
```

### 5. Execute o sistema
```bash
python app.py
```

### 6. Acesse o sistema
- **Local**: http://localhost:5000
- **Login padrão**: admin / admin123

## 📡 Configuração de Acesso Remoto

### Opção 1: Port Forwarding no Roteador

1. **Descubra o IP local do seu PC**:
   ```bash
   ipconfig  # Windows
   ifconfig  # Linux/Mac
   ```

2. **Configure o roteador**:
   - Acesse o painel do roteador (geralmente 192.168.1.1)
   - Vá para "Port Forwarding" ou "Redirecionamento de Portas"
   - Configure:
     - Porta externa: 5000
     - Porta interna: 5000
     - IP interno: [IP do seu PC]
     - Protocolo: TCP

3. **Descubra seu IP público**:
   ```bash
   curl ifconfig.me
   ```

4. **Acesse remotamente**:
   ```
   http://[SEU_IP_PUBLICO]:5000
   ```

### Opção 2: DNS Dinâmico (No-IP - Gratuito)

1. Crie conta em: https://www.noip.com
2. Configure um hostname gratuito
3. Instale o cliente No-IP no seu PC
4. Acesse via: http://seuhostname.no-ip.org:5000

## 🔧 Configuração da Câmera RTSP

### Formatos comuns de URL RTSP:

```
# Hikvision/Dahua
rtsp://usuario:senha@192.168.1.100:554/Streaming/Channels/101

# Genericas
rtsp://usuario:senha@192.168.1.100:554/stream1
rtsp://192.168.1.100:554/user=admin&password=senha&channel=1&stream=0.sdp

# Com autenticação básica
rtsp://192.168.1.100:554/live/ch00_0
```

### Como descobrir a URL RTSP da sua câmera:

1. **Manual da câmera**: Procure por "RTSP URL"
2. **Interface web**: Acesse as configurações da câmera
3. **Apps móveis**: Use apps como "ONVIF" ou "Fing"
4. **Teste com VLC**: Abra VLC → Mídia → Abrir Fluxo de Rede

## 🛡️ Segurança

### Mudar senha padrão
Edite `config.py`:
```python
SECURITY = {
    'username': 'seu_usuario',
    'password_hash': None,  # Será gerado automaticamente na primeira execução
}
```

### HTTPS com certificado autoassinado (Opcional)
```bash
# Gerar certificado
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Modificar app.py para usar HTTPS
# Adicione: app.run(ssl_context=('cert.pem', 'key.pem'))
```

### Firewall do Windows
```bash
# Abrir porta 5000 no firewall
netsh advfirewall firewall add rule name="Sistema Vigilancia IA" dir=in action=allow protocol=TCP localport=5000
```

## 📋 Requisitos Mínimos

- **Sistema**: Windows 10/11, Linux ou macOS
- **Python**: 3.8 ou superior
- **Memória RAM**: 4GB (mínimo)
- **CPU**: Intel i3 ou equivalente (para detecção em tempo real)
- **GPU**: Opcional (melhora performance do YOLOv8)
- **Rede**: Conexão com a câmera RTSP

## 🎯 Personalização

### Ajustar sensibilidade de detecção
Edite `config.py`:
```python
MOTION_DETECTION = {
    'min_area': 500,      # Aumente para reduzir falsos positivos
    'var_threshold': 16,  # Ajuste a sensibilidade
}

YOLO = {
    'confidence': 0.5,     # Confiança mínima (0.0 a 1.0)
}
```

### Horários de funcionamento
```python
SCHEDULE = {
    'enabled': True,
    'active_hours': {
        'start': '22:00',
        'end': '06:00'
    }
}
```

### Alertas por Telegram
```python
TELEGRAM = {
    'enabled': True,
    'bot_token': 'SEU_BOT_TOKEN',
    'chat_id': 'SEU_CHAT_ID',
}
```

## 🐛 Solução de Problemas

### Câmera não conecta
1. Verifique a URL RTSP com VLC
2. Confirme usuário e senha
3. Teste na mesma rede local primeiro
4. Verifique firewall/antivírus

### Performance lenta
1. Reduza a resolução da câmera
2. Aumente `detection_cooldown` em config.py
3. Use modelo YOLO menor (`yolov8n.pt` já está configurado)
4. Desative detecção de movimento se não necessário

### Erros de dependências
```bash
# Atualizar pip
python -m pip install --upgrade pip

# Reinstalar dependências
pip uninstall opencv-python ultralytics flask
pip install -r requirements.txt
```

## 📁 Estrutura de Arquivos

```
meu_site_ai_rtsp/
├── app.py                    # Aplicação principal Flask
├── config.py                 # Configurações do sistema
├── requirements.txt          # Dependências Python
├── templates/
│   ├── login.html           # Página de login
│   └── index.html           # Dashboard principal
├── static/
│   └── style.css            # Estilos CSS
├── alerts/                  # Imagens de alerta salvas
├── recordings/              # Vídeos gravados (se ativado)
└── yolov8n.pt              # Modelo YOLO (baixado automaticamente)
```

## 🚀 Recursos Avançados (Opcionais)

### 1. Gravação Automática
Ative em `config.py`:
```python
RECORDING = {
    'enabled': True,
    'record_on_person_detection': True,
    'record_duration': 30,
}
```

### 2. Whitelist de IPs
```python
IP_WHITELIST = {
    'enabled': True,
    'allowed_ips': ['192.168.1.0/24', 'seu_ip_externo'],
}
```

### 3. Integração com Home Assistant
Use o endpoint `/status` para integrar com automações.

## 📞 Suporte

### Comandos úteis para debug:
```bash
# Ver logs em tempo real
tail -f system.log

# Testar conexão RTSP
ffprobe -v quiet -print_format json -show_streams rtsp://sua_url

# Ver processos Python
ps aux | grep python

# Matar processo se travar
taskkill /F /PID [numero_do_processo]  # Windows
kill -9 [numero_do_processo]            # Linux/Mac
```

## ⚠️ Avisos Importantes

1. **Segurança**: Sempre mude a senha padrão!
2. **Privacidade**: Respeite leis locais sobre vigilância
3. **Rede**: Use VPN para acesso remoto adicional
4. **Armazenamento**: Monitore espaço em disco (alertas e gravações)
5. **Atualizações**: Mantenha o sistema e dependências atualizadas

---

**💡 Dica**: Teste tudo localmente antes de configurar o acesso remoto!

**🆓 100% Gratuito**: Este sistema não reere nenhum pagamento ou assinatura.