# Dashboard ZAS — Deploy en GitHub Pages

## Link público (una vez configurado)
```
https://martinaboazzocid.github.io/zas-dashboard/dashboard_talentos.html
```

---

## Setup inicial (una sola vez, ~15 minutos)

### 1. Crear el repositorio en GitHub
- Entrá a github.com con tu cuenta `martinaboazzocid`
- New repository → nombre: `zas-dashboard` → **Public** → Create

### 2. Subir estos archivos al repositorio
En tu computadora, abrí PowerShell en esta carpeta y corré:

```powershell
git init
git add .
git commit -m "setup inicial"
git branch -M main
git remote add origin https://github.com/martinaboazzocid/zas-dashboard.git
git push -u origin main
```

### 3. Guardar la password de Odoo como Secret
- En el repositorio: Settings → Secrets and variables → Actions → New repository secret
- Nombre: `ODOO_PASS`
- Valor: tu password de Odoo
- → Add secret

### 4. Activar GitHub Pages
- En el repositorio: Settings → Pages
- Source: **Deploy from a branch**
- Branch: `gh-pages` → `/ (root)` → Save

### 5. Verificar que funciona
- Actions → "Dashboard ZAS — Actualización diaria" → Run workflow
- Esperá ~5 minutos
- Entrá al link del paso 1

---

## Horario
Corre automáticamente todos los días a las **10:30 AM Argentina (ART)**.

## Correr manualmente
GitHub → Actions → "Dashboard ZAS" → Run workflow

## Ver logs de cada corrida
GitHub → Actions → click en la corrida → "generar"
