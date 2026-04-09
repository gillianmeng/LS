from django import forms
from django.forms import SplitDateTimeWidget

from .models import MallOrder, MallShippingAddress, ShopMallSettings, Training


def _training_split_datetime_widget():
    """拆分日期 + 时间，避免部分环境下整段 datetime 只给「现在/午夜/整点」等固定选项；时间可任选时分。"""
    return SplitDateTimeWidget(
        date_attrs={"type": "date", "class": "vDateField"},
        time_attrs={"type": "time", "step": "60", "class": "vTimeField"},
    )


class TrainingAdminForm(forms.ModelForm):
    """后台培训活动：时间字段用日期+时间分开填写，便于精确到任意时分。"""

    class Meta:
        model = Training
        fields = "__all__"
        widgets = {
            "start_at": _training_split_datetime_widget(),
            "end_at": _training_split_datetime_widget(),
            "registration_deadline": _training_split_datetime_widget(),
            "applications_category": forms.RadioSelect,
        }


class ShopMallSettingsForm(forms.ModelForm):
    """后台「积分商城：规则与说明」单页编辑表单。"""

    class Meta:
        model = ShopMallSettings
        fields = (
            "points_earn_rules",
            "points_daily_login",
            "points_course_complete_default",
            "points_learning_daily_cap",
            "default_pickup_instruction",
        )
        widgets = {
            "points_earn_rules": forms.Textarea(
                attrs={
                    "rows": 16,
                    "cols": 80,
                    "class": "vLargeTextField",
                    "style": "width: min(100%, 52rem); min-height: 14rem;",
                    "placeholder": "每条一行。前 3 行 → 前台三张规则卡片；第 4 行起 → 下方补充说明。\n留空则使用系统内置默认规则。",
                }
            ),
            "default_pickup_instruction": forms.Textarea(
                attrs={
                    "rows": 5,
                    "cols": 80,
                    "class": "vLargeTextField",
                    "style": "width: min(100%, 52rem);",
                }
            ),
        }


class MallCheckoutForm(forms.Form):
    delivery_type = forms.ChoiceField(
        label="领取方式",
        choices=MallOrder.DeliveryType.choices,
        widget=forms.RadioSelect,
        initial=MallOrder.DeliveryType.MAIL,
    )
    recipient_name = forms.CharField(
        label="收件人姓名",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"}),
    )
    recipient_phone = forms.CharField(
        label="联系电话",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm", "placeholder": "11 位手机号"}),
    )
    address_detail = forms.CharField(
        label="收件地址",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm",
                "placeholder": "省 / 市 / 区及街道、门牌号",
            }
        ),
    )
    pickup_location_note = forms.CharField(
        label="领取说明（选填）",
        max_length=2000,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm",
                "placeholder": "不填则使用后台「积分商城：规则与说明」中的默认现场领取说明；填写则整段作为本单领取说明。",
            }
        ),
    )
    buyer_remark = forms.CharField(
        label="订单备注",
        max_length=500,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm",
                "placeholder": "颜色、尺码等需求（如有）",
            }
        ),
    )
    save_address = forms.BooleanField(
        label="将本单收件信息保存为默认收货地址（仅邮寄）",
        required=False,
        initial=True,
    )

    def clean(self):
        data = super().clean()
        dt = data.get("delivery_type")
        if dt == MallOrder.DeliveryType.MAIL:
            if not (data.get("recipient_name") or "").strip():
                self.add_error("recipient_name", "邮寄订单请填写收件人。")
            if not (data.get("recipient_phone") or "").strip():
                self.add_error("recipient_phone", "邮寄订单请填写联系电话。")
            if not (data.get("address_detail") or "").strip():
                self.add_error("address_detail", "邮寄订单请填写完整收件地址。")
        elif dt == MallOrder.DeliveryType.PICKUP:
            if not (data.get("recipient_name") or "").strip():
                self.add_error("recipient_name", "请填写领取人姓名。")
            if not (data.get("recipient_phone") or "").strip():
                self.add_error("recipient_phone", "请填写联系电话，便于通知领取。")
        return data


class MallShippingAddressForm(forms.ModelForm):
    class Meta:
        model = MallShippingAddress
        fields = ("label", "recipient_name", "recipient_phone", "address_detail", "is_default")
        labels = {
            "label": "标签（选填）",
            "recipient_name": "收件人",
            "recipient_phone": "联系电话",
            "address_detail": "详细地址",
            "is_default": "设为默认",
        }
        widgets = {
            "label": forms.TextInput(
                attrs={"class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm", "placeholder": "如：家、公司"}
            ),
            "recipient_name": forms.TextInput(attrs={"class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"}),
            "recipient_phone": forms.TextInput(attrs={"class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"}),
            "address_detail": forms.Textarea(
                attrs={"rows": 3, "class": "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"}
            ),
            "is_default": forms.CheckboxInput(attrs={"class": "rounded border-slate-300 text-sky-600"}),
        }
