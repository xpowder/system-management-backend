"""Local printable cash receipts (HTML + PDF)."""
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from bookings.models import BookingPayment


def receipt_context(payment: BookingPayment) -> dict:
    booking = payment.booking
    client = booking.client.user
    provider = booking.provider
    return {
        "company": "HOMEZUP",
        "booking_id": booking.id,
        "client": f"{client.first_name} {client.last_name}".strip() or client.username,
        "property": booking.property_ref.name,
        "provider": provider.company_name
        or f"{provider.user.first_name} {provider.user.last_name}".strip()
        or provider.user.username,
        "payment_date": payment.received_at,
        "amount_paid": payment.amount,
        "payment_method": payment.get_payment_method_display(),
        "total_booking_price": booking.total_price,
        "total_paid": booking.total_paid,
        "remaining_balance": booking.remaining_balance,
        "received_by": payment.received_by_user,
        "receipt_number": payment.receipt_number,
        "currency": "MAD",
        "notes": payment.notes,
    }


def render_receipt_html(payment: BookingPayment) -> str:
    return render_to_string("bookings/receipt.html", receipt_context(payment))


def receipt_html_response(payment: BookingPayment) -> HttpResponse:
    html = render_receipt_html(payment)
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def receipt_pdf_response(payment: BookingPayment) -> HttpResponse:
    data = receipt_context(payment)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(25 * mm, y, "HOMEZUP")
    y -= 10 * mm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(25 * mm, y, "Cash receipt")
    y -= 12 * mm

    lines = [
        f"Receipt: {data['receipt_number']}",
        f"Booking ID: {data['booking_id']}",
        f"Client: {data['client']}",
        f"Property: {data['property']}",
        f"Provider: {data['provider']}",
        f"Payment date: {data['payment_date']}",
        f"Amount paid: {data['amount_paid']} {data['currency']}",
        f"Payment method: {data['payment_method']}",
        f"Total booking price: {data['total_booking_price']} {data['currency']}",
        f"Total paid: {data['total_paid']} {data['currency']}",
        f"Remaining balance: {data['remaining_balance']} {data['currency']}",
        f"Received by: {data['received_by']}",
    ]
    for line in lines:
        pdf.drawString(25 * mm, y, line)
        y -= 8 * mm

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="homezup-receipt-{payment.receipt_number}.pdf"'
    )
    return response
