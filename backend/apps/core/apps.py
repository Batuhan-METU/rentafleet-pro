"""Proje çekirdeği — iş mantığı DEĞİL, altyapı kabuğu.

``core`` modülünün görevleri:
  * **Migration geçmişi** — Django app label ``api`` (mevcut DB tabloları: ``api_*``)
  * **Kök URL yönlendirme** — ``api.py`` altında ``/admin`` ve ``/api/...``
  * **Sağlık kontrolü** — ``GET /api/health/``

Domain modelleri, view'lar ve serializer'lar kendi app'lerinde yaşar
(``companies``, ``vehicles``, ``customer_profiles``, …). ``core`` bunları toplamaz.

ÖNEMLİ — ``app_label`` kuralı: Proje, düz bir ``api`` app'inden bugünkü
katmanlı yapıya (``backend/apps/<domain>/``) refactor edildi ancak migration
geçmişi ve DB tablo adları (``api_*``) geriye dönük uyumluluk için ``api``
etiketinde bırakıldı (bkz. ``backend.settings.MIGRATION_MODULES``). Bu yüzden
``backend/apps/<domain>/models*.py`` altındaki HER model ``class Meta:
app_label = "api"`` bildirmelidir — aksi halde Django modeli kendi app
config'inin etiketine (örn. ``vehicles``) bağlamaya çalışır ve migration
geçmişiyle uyuşmayan yeni bir app/tablo seti oluşturmaya kalkışır.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.core"
    label = "api"
    verbose_name = "Proje çekirdeği"
