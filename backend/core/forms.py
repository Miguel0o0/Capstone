from django import forms
from .models import Payment, Fee


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["resident", "fee", "status", "paid_at"]
        widgets = {
            "paid_at": forms.DateInput(attrs={"type": "date"}),
        }

        labels = {
            "resident": "Vecino",
            "fee": "Cuota",
            "status": "Estado",
            "paid_at": "Fecha de pago",
        }

    def __init__(self, *args, **kwargs):
        # recibimos la request para saber el rol
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # ordenar cuotas como prefieras
        self.fields["fee"].queryset = Fee.objects.all().order_by("-id")

        # Si es vecino (no admin/secretario), escondemos 'resident'
        # y limitamos 'status' solo a "Pendiente".
        if self.request:
            u = self.request.user
            is_admin = (
                u.is_superuser
                or u.groups.filter(name__in=["Admin", "Secretario"]).exists()
            )

            if not is_admin:
                # vecino: no puede elegir otro residente
                self.fields["resident"].initial = u
                self.fields["resident"].widget = forms.HiddenInput()

                # vecino: no puede marcar pagado
                # (usa las constantes del modelo Payment)
                label_map = dict(Payment.STATUS_CHOICES)
                self.fields["status"].choices = [
                    (Payment.STATUS_PENDING, label_map[Payment.STATUS_PENDING])
                ]
