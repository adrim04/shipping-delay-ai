# Guía: publicar el repositorio y obtener evidencia de revisión de PR con IA

## 1. Crear el repositorio público
1. En GitHub → **New repository** → nombre `shipping-delay-ai` → **Public** → sin README (ya existe).
2. En tu computadora, dentro de la carpeta del proyecto:
```bash
git init
git add .
git commit -m "feat: servicio de IA, cliente web y documentación CRISP-ML(Q)"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/shipping-delay-ai.git
git push -u origin main
```
3. La URL a entregar es `https://github.com/<tu-usuario>/shipping-delay-ai`.
4. En la pestaña **Actions** verás el workflow **CI** (lint + pytest) en verde.

## 2. Activar la IA de revisión de código (elige una)
**Opción A – CodeRabbit (gratis para repos públicos)**
1. Entra a https://coderabbit.ai → *Sign in with GitHub* → autoriza la app solo para `shipping-delay-ai`.
2. El archivo `.coderabbit.yaml` del repo ya la configura en español y con instrucciones de revisión de ML.

**Opción B – GitHub Copilot code review** (si tienes Copilot, gratis con GitHub Student Pack)
1. En el PR → panel **Reviewers** → elige **Copilot**.

## 3. Generar la evidencia (un PR real)
```bash
git checkout -b feature/filtro-historial-por-modelo
# haz un cambio pequeño, p. ej. agregar el parámetro model_version al GET /predictions
git add . && git commit -m "feat(api): filtrar historial por versión del modelo"
git push -u origin feature/filtro-historial-por-modelo
```
1. En GitHub → **Compare & pull request** → completa la plantilla (ya viene precargada) → **Create pull request**.
2. Espera 2-5 minutos: CodeRabbit (o Copilot) publica un resumen y comentarios en las líneas.
3. Responde/aplica al menos una sugerencia (commit adicional) y luego **Merge**.
4. **Evidencia:** captura del resumen de la IA, de un comentario en línea y del check de CI en verde,
   más el enlace al PR (`https://github.com/<usuario>/shipping-delay-ai/pull/1`).

> Ideas de PR pequeños que suelen generar buenos comentarios: agregar el filtro por versión,
> agregar paginación a `/models`, o permitir ajustar el umbral de decisión (0.5) por configuración.
