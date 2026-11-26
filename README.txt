========================================================================
SISTEMA WEB TIENDA "CALZADOS IMPORT" - INGENIERÍA DE SISTEMAS I (UPEA)
========================================================================

PASOS PARA EJECUTAR EL PROYECTO EN TU EQUIPO:

1. DESCOMPRIMIR EL ARCHIVO ZIP.
2. ABRE GIT BASH O TU TERMINAL DENTRO DE LA CARPERTA "calzados_import".
3. CREAR Y ACTIVAR EL ENTORNO VIRTUAL:
   python -m venv venv
   source venv/Scripts/activate   (en Git Bash)
   o bien: venv\Scripts\activate (en CMD)

4. INSTALAR DEPENDENCIAS:
   pip install -r requirements.txt

5. CREAR LA BASE DE DATOS EN POSTGRESQL (pgAdmin):
   - Abre pgAdmin o psql.
   - Crea una base de datos llamada: calzados_import_db
   - Edita el archivo "config/settings.py" y pon tu contraseña de PostgreSQL en DATABASES['default']['PASSWORD'].

6. MIGRAR TABLAS Y CREAR SUPERUSUARIO:
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser

7. ASIGNAR ROL DE ADMINISTRADOR Y CATEGORÍAS INICIALES:
   Abre la consola interactiva de Django:
   python manage.py shell

   Copia y pega estas líneas en la consola:
   from django.contrib.auth.models import User
   from tienda.models import PerfilUsuario, Categoria
   u = User.objects.first()
   PerfilUsuario.objects.get_or_create(usuario=u, defaults={'rol': 'ADMIN'})
   for cat in ['Damas', 'Varones', 'Niños', 'Deportivo', 'Casual']:
       Categoria.objects.get_or_create(nombre=cat)
   exit()

8. INICIAR EL SERVIDOR WEB:
   python manage.py runserver

9. ACCEDER DESDE TU NAVEGADOR:
   http://127.0.0.1:8000/
========================================================================
