# trending.ai — Content Agent (mi parte)

Agente que toma tendencias sociales (extraídas de Polymarket por el pipeline de
tvesah), **genera contenido visual con Magnific** y lo somete a **aprobación
humana por Gmail** antes de darlo por bueno.

Stack: **Google ADK** (agente) + **Vertex AI** (LLM) + **Magnific MCP** (generación) + **Gmail API** (human-in-the-loop).

## Flujo

```
trends_input/trends.json        (lo deja tvesah)
        │  load_trends
        ▼
  images_generate (Magnific MCP)  ──► URL de la imagen
        │  send_review_email
        ▼
  📧 Gmail al revisor  ── responde: APROBAR / DENEGAR / EDITAR: <cambios>
        │  wait_for_review_reply (polling del hilo)
        ▼
  el LLM interpreta la respuesta
   ├─ EDITAR  → regenera y vuelve a pedir revisión (máx. 3 vueltas)
   ├─ APROBAR → save_approved  → output/approved/<id>.json   ✓ FIN
   └─ DENEGAR → descarta                                      ✓ FIN
```

> El alcance termina en el loop de Gmail. **No** publica a redes.

## Estructura

```
content_agent/
├── agent.py            # root_agent (LlmAgent) + MCPToolset de Magnific
├── prompts.py          # instrucción de orquestación
├── tools/
│   ├── trends.py       # load_trends  (lee el JSON de tvesah)
│   └── gmail_review.py # send_review_email / wait_for_review_reply / save_approved
└── .env.example        # copiar a .env
trends_input/trends.json  # contrato con tvesah (ejemplo incluido)
```

## Setup

1. **Dependencias**
   ```bash
   pip install -r requirements.txt
   # Node ya disponible para `npx mcp-remote` (Magnific)
   ```

2. **Credenciales**
   - **Vertex:** coloca tu service account JSON como `service_account.json`.
   - **Gmail:** descarga un *OAuth client ID* tipo **Desktop** de Google Cloud
     Console y guárdalo como `credentials.json`. La 1ª corrida abre el navegador
     y crea `token.json`.
   - **Magnific:** no necesitas API key; el primer `npx mcp-remote` abre el
     navegador para el sign-in de Magnific y cachea el token.

3. **Config**
   ```bash
   cp content_agent/.env.example content_agent/.env
   # edita GOOGLE_CLOUD_PROJECT, location, etc.
   ```

## Correr

```bash
adk web        # UI local en http://localhost:8000  → elige "content_agent"
# o
adk run content_agent
```

Pídele: *"Procesa la primera tendencia"*. Revisa tu Gmail, responde el correo
(APROBAR / DENEGAR / EDITAR: ...) y observa cómo el agente reacciona.

## Contrato con tvesha (`trends_input/trends.json`)

| campo          | descripción                                        |
|----------------|----------------------------------------------------|
| `id`           | id estable de la tendencia                          |
| `topic`        | título/tema                                          |
| `summary`      | resumen de la tendencia de Polymarket               |
| `angle`        | ángulo/tono editorial deseado                        |
| `platform`     | red destino (twitter, instagram, ...)               |
| `content_type` | `image` (o `video`)                                  |
| `hashtags`     | lista de hashtags                                    |
| `visual_prompt`| prompt visual para Magnific                          |
