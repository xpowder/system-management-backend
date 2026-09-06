"""Printable cash receipts for gym payments."""
from base64 import b64encode
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import content_disposition_header
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from fitness.attendance import member_qr_code
from fitness.exports import COMPANY, CURRENCY, _money_text
from fitness.models import ClassMember


def receipt_number(payment) -> str:
    return f'FO-{payment.id:06d}'


def _qr_svg_b64(member) -> str:
    qr = member_qr_code(member)
    if qr is None:
        return ''
    buffer = BytesIO()
    qr.save(buffer, kind='svg', scale=5, border=1)
    return b64encode(buffer.getvalue()).decode('ascii')


def _draw_qr(pdf, qr, x, y, size):
    matrix = getattr(qr, 'matrix', None)
    if not matrix:
        return
    rows = len(matrix)
    cols = len(matrix[0])
    cell = size / max(rows, cols)
    pdf.saveState()
    pdf.setFillColorRGB(0, 0, 0)
    for row_index, row in enumerate(matrix):
        for col_index, dark in enumerate(row):
            if dark:
                pdf.rect(
                    x + col_index * cell,
                    y + (rows - 1 - row_index) * cell,
                    cell,
                    cell,
                    stroke=0,
                    fill=1,
                )
    pdf.restoreState()


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
        'amount_text': _money_text(payment.amount),
        'received_by': payment.received_by,
        'currency': CURRENCY,
        'qr_svg_b64': _qr_svg_b64(member),
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
    left = 22 * mm
    right = width - 22 * mm
    y = height - 22 * mm

    pdf.setFillColorRGB(0.937, 0.455, 0.361)
    pdf.rect(left, y - 10 * mm, 10 * mm, 10 * mm, stroke=0, fill=1)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawCentredString(left + 5 * mm, y - 7 * mm, (data['company'] or 'A')[:1])

    pdf.setFillColorRGB(0.09, 0.13, 0.15)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(left + 14 * mm, y - 2 * mm, 'CASH RECEIPT')
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(left + 14 * mm, y - 9 * mm, data['company'])

    qr = member_qr_code(payment.membership.member)
    if qr is not None:
        size = 28 * mm
        _draw_qr(pdf, qr, right - size, y - size + 2 * mm, size)
        pdf.setFont('Helvetica', 7)
        pdf.setFillColorRGB(0.29, 0.38, 0.34)
        pdf.drawRightString(right, y - size - 3 * mm, 'Member QR')

    y -= 18 * mm
    pdf.setStrokeColorRGB(0.09, 0.13, 0.15)
    pdf.setLineWidth(1.4)
    pdf.line(left, y, right, y)

    y -= 12 * mm
    pdf.setFillColorRGB(0.29, 0.38, 0.34)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(left, y, 'RECEIVED FROM')
    y -= 8 * mm
    pdf.setFillColorRGB(0.09, 0.13, 0.15)
    pdf.setFont('Helvetica-Bold', 18)
    name = f"{data['first_name']} {data['last_name']}".strip() or 'Member'
    pdf.drawString(left, y, name[:42])
    y -= 6 * mm
    pdf.setFont('Helvetica', 11)
    pdf.setFillColorRGB(0.29, 0.38, 0.34)
    pdf.drawString(left, y, str(data['class_name'])[:48])

    y -= 14 * mm
    pdf.setFillColorRGB(0.953, 0.961, 0.945)
    pdf.rect(left, y - 10 * mm, right - left, 16 * mm, stroke=0, fill=1)
    pdf.setFillColorRGB(0.937, 0.455, 0.361)
    pdf.rect(left, y - 10 * mm, 1.6 * mm, 16 * mm, stroke=0, fill=1)
    pdf.setFillColorRGB(0.29, 0.38, 0.34)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(left + 6 * mm, y + 1 * mm, 'AMOUNT PAID')
    pdf.setFillColorRGB(0.09, 0.13, 0.15)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawRightString(right - 5 * mm, y - 5 * mm, data['amount_text'])

    y -= 20 * mm
    rows = [
        ('Receipt', data['receipt_number']),
        ('First name', data['first_name']),
        ('Last name', data['last_name']),
        ('Class', data['class_name']),
        ('Date', data['payment_date']),
        ('Time', data['payment_time']),
        ('Received by', data['received_by']),
        ('Method', 'Cash'),
    ]
    pdf.setStrokeColorRGB(0.839, 0.867, 0.847)
    pdf.setLineWidth(0.6)
    for label, value in rows:
        pdf.setFillColorRGB(0.29, 0.38, 0.34)
        pdf.setFont('Helvetica', 9)
        pdf.drawString(left, y, str(label))
        pdf.setFillColorRGB(0.09, 0.13, 0.15)
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(left + 42 * mm, y, str(value)[:48])
        pdf.line(left, y - 3 * mm, right, y - 3 * mm)
        y -= 9 * mm

    y -= 6 * mm
    pdf.setFillColorRGB(0.29, 0.38, 0.34)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(left, y, 'Thank you. Keep this receipt for your records.')
    y -= 4 * mm
    pdf.drawString(left, y, 'Scan the Member QR at reception to check in.')

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = content_disposition_header(
        True, f"AUMB-receipt-{data['receipt_number']}.pdf"
    )
    return response
