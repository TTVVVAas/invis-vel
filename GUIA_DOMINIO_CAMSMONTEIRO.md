# 🌐 Guia de Configuração: camsmonteiro.ddns.net

## ✅ Status Atual
- **Domínio**: camsmonteiro.ddns.net
- **IP Público**: 89.114.2.135
- **IP Local**: 192.168.1.152
- **Porta**: 5000
- **Sistema de Gravações**: ✅ Ativo (2 vídeos)

## 🔗 URLs de Acesso
- **Local**: http://127.0.0.1:5000/recordings
- **Rede Local**: http://192.168.1.152:5000/recordings
- **Domínio Externo**: http://camsmonteiro.ddns.net:5000/recordings

## 🚀 Configuração Concluída

### 1. ✅ Servidor Flask
- Configurado para `host='0.0.0.0'` (aceita conexões externas)
- Porta 5000
- Threaded mode ativado

### 2. ✅ Firewall do Windows
- Porta 5000 liberada para entrada TCP
- Regra: "Flask RTSP Server"

### 3. ✅ Sistema de Gravações
- **2 vídeos gravados** em `2025/11_Novembro/10/`
- Organização automática por data
- Interface web completa
- API REST funcional

## 📋 Próximos Passos Necessários

### 🔧 1. Configuração do Roteador
**Acesso ao roteador**: Geralmente http://192.168.1.1 ou http://192.168.0.1

**Configurações necessárias**:
1. **Port Forwarding/Redirecionamento de Porta**:
   - Porta externa: 5000
   - Porta interna: 5000
   - IP interno: 192.168.1.152
   - Protocolo: TCP

2. **DDNS (Dynamic DNS)**:
   - Seu domínio: camsmonteiro.ddns.net
   - Verificar se está atualizado com IP 89.114.2.135

### 🔒 2. Segurança Recomendada

#### Alterar senhas padrão:
```bash
# Criar novo usuário admin (recomendado)
python -c "
from app import app, db, User
with app.app_context():
    admin = User(username='seu_usuario')
    admin.set_password('sua_senha_segura')
    db.session.add(admin)
    db.session.commit()
    print('✅ Novo usuário criado com sucesso!')
"
```

#### Configurar HTTPS (Opcional):
- Usar nginx como proxy reverso
- Configurar certificado SSL
- Redirecionar porta 80 para 5000

## 🧪 Testes de Acesso

### Testar localmente:
```bash
curl http://127.0.0.1:5000/login
```

### Testar rede local:
- Abrir no celular: http://192.168.1.152:5000/recordings

### Testar acesso externo:
- Acessar: http://camsmonteiro.ddns.net:5000/recordings

## 📁 Estrutura de Gravações
```
recordings/
└── 2025/
    └── 11_Novembro/
        └── 10/
            ├── clip_15-20h10-11-25.mp4
            └── clip_15-40h10-11-25.mp4
```

## 🎥 Funcionalidades Disponíveis

### Interface Web:
- ✅ Visualizar gravações por data
- ✅ Download de vídeos
- ✅ Preview em tempo real
- ✅ Sistema de login

### API REST:
- ✅ `/api/recordings` - Listar todas as gravações
- ✅ `/api/recordings/download/<path>` - Download de vídeo
- ✅ `/api/system/status` - Status do sistema

## 🛠️ Comandos Úteis

### Verificar se servidor está rodando:
```bash
python -c "import requests; print('✅ OK' if requests.get('http://127.0.0.1:5000/login').status_code == 200 else '❌ OFF')"
```

### Verificar gravações:
```bash
python verificar_dominio.py
```

### Reiniciar servidor:
```bash
# Parar servidor atual: Ctrl+C
python app.py
```

## ⚠️ Problemas Comuns

### 1. Erro "Conexão recusada"
- Verificar se o servidor está rodando
- Verificar firewall
- Verificar porta 5000

### 2. Domínio não responde
- Verificar DDNS atualizado
- Verificar redirecionamento de porta
- Verificar IP público

### 3. Página de login não carrega
- Verificar se arquivo `templates/login.html` existe
- Verificar logs do Flask

## 📞 Suporte
Se tiver problemas:
1. Verifique os logs do terminal onde rodou `python app.py`
2. Execute `python verificar_dominio.py` para diagnóstico
3. Confirme que o DDNS está atualizado com seu IP atual

---
**Status**: ✅ Sistema configurado e pronto para acesso externo!