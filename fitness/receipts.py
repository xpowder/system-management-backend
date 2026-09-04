"""Printable cash receipts for gym payments."""
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import content_disposition_header
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from fitness.exports import COMPANY, CURRENCY, _money_text
from fitness.models import ClassMember


def receipt_number(payment) -> str:
    return f'FO-{payment.id:06d}'


def receipt_context(payment) -> dict:
    member = payment.membership.member
    user = member.user
    stamp = timezone.localtime(payment.received_at) if timezone.is_aware(payment.received_at) else payment.received_at
    assignment = (
        ClassMember.objects.filter(client_id=member.id, is_active=True)
        .select_related('training_class')
        .first()
    )
    return {
        'company': COMPANY,
        'receipt_number': receipt_number(payment),
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'class_name': assignment.training_class.name if assignment else 'No class',
        'payment_date': stamp.strftime('%d %b %Y'),
        'payment_time': stamp.strftime('%H:%M'),
        'amount_paid': payment.amount,
        'received_by': payment.received_by,
        'currency': CURRENCY,
    }


def render_receipt_html(payment) -> str:
    return render_to_string('fitness/receipt.html', receipt_context(payment))


def receipt_html_response(payment) -> HttpResponse:
    return HttpResponse(render_receipt_html(payment), content_type='text/html; charset=utf-8')


def receipt_pdf_response(payment) -> HttpResponse:
    data = receipt_context(payment)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(25 * mm, y, COMPANY)
    y -= 8 * mm
    pdf.setFont('Helvetica', 11)
    pdf.drawString(25 * mm, y, 'Cash receipt')
    y -= 12 * mm

    lines = [
        f"First name: {data['first_name']}",
        f"Last name: {data['last_name']}",
        f"Class: {data['class_name']}",
        f"Date: {data['payment_date']}",
        f"Time: {data['payment_time']}",
        f"Amount paid: {_money_text(data['amount_paid'])}",
        f"Received by: {data['received_by']}",
    ]
    for line in lines:
        pdf.drawString(25 * mm, y, str(line)[:90])
        y -= 8 * mm

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = content_disposition_header(
        True, f"AUMB-receipt-{data['receipt_number']}.pdf"
    )
    return response
