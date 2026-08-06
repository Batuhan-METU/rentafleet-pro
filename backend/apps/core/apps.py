"""Proje çekirdeği — iş mantığı DEĞİL, altyapı kabuğu.

``core`` modülünün görevleri:
  * **Kök URL yönlendirme** — ``urls.py`` altında (ROOT_URLCONF) ``/admin`` ve ``/api/...``
  * **Sağlık kontrolü** — ``GET /api/health/``

Domain modelleri, view'lar ve serializer'lar kendi app'lerinde yaşar
(``companies``, ``vehicles``, ``customer_profiles``, …). ``core`` bunları toplamaz
ve kendi migration geçmişi yoktur (``models.py`` içermez).

Not — DB tablo adları hâlâ tarihsel ``api_*`` önekini taşır (her modelin
``Meta.db_table``'ında sabitlenmiştir), ancak Django ``app_label`` artık her
model kendi app'ine (``companies``, ``vehicles``, ``risk_checks``, …) aittir;
eski paylaşımlı ``api`` etiketi ve ``backend/migrations/`` klasörü kaldırıldı.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.core"
    label = "core"
    verbose_name = "Proje çekirdeği"
