from flask import Flask, render_template, request, jsonify, send_file
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import io
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["bill_me_db"]
products_col = db["products"]
stock_col = db["stock"]
bills_col = db["bills"]

# ─── AUTH ───────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if data.get("username") == "bill" and data.get("password") == "bill@123":
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

# ─── PRODUCTS ───────────────────────────────────────────
@app.route("/api/products", methods=["GET"])
def get_products():
    products = list(products_col.find({}, {"_id": 0}))
    return jsonify(products)

@app.route("/api/products/search", methods=["GET"])
def search_products():
    q = request.args.get("q", "")
    products = list(products_col.find(
        {"name": {"$regex": f"^{q}", "$options": "i"}},
        {"_id": 0, "name": 1, "price": 1, "product_id": 1}
    ))
    return jsonify(products)

@app.route("/api/products/add", methods=["POST"])
def add_product():
    data = request.json
    required = ["name", "manufacturer_name", "manufacturer_address",
                "manufacturer_contact", "type", "price"]
    for f in required:
        if not data.get(f):
            return jsonify({"success": False, "message": f"Missing field: {f}"}), 400

    pid = "P" + str(int(datetime.now().timestamp() * 1000))[-6:]
    product = {
        "product_id": pid,
        "name": data["name"],
        "manufacturer_name": data["manufacturer_name"],
        "manufacturer_address": data["manufacturer_address"],
        "manufacturer_contact": data["manufacturer_contact"],
        "type": data["type"],
        "price": float(data["price"]),
        "description": data.get("description", ""),
        "has_expiry": data.get("has_expiry", False),
        "created_at": datetime.utcnow().isoformat()
    }
    products_col.insert_one(product)
    return jsonify({"success": True, "product_id": pid})

# ─── STOCK ──────────────────────────────────────────────
@app.route("/api/stock", methods=["GET"])
def get_stock():
    pipeline = [
        {"$group": {
            "_id": "$product_id",
            "total_qty": {"$sum": "$quantity"},
            "latest": {"$last": "$$ROOT"}
        }},
        {"$lookup": {
            "from": "products",
            "localField": "_id",
            "foreignField": "product_id",
            "as": "product"
        }},
        {"$unwind": "$product"}
    ]
    result = list(stock_col.aggregate(pipeline))
    out = []
    for r in result:
        out.append({
            "product_id": r["_id"],
            "product_name": r["product"]["name"],
            "type": r["product"]["type"],
            "total_qty": r["total_qty"],
            "price": r["latest"].get("price", r["product"]["price"]),
            "expiry_date": r["latest"].get("expiry_date", None),
            "has_expiry": r["product"]["has_expiry"]
        })
    return jsonify(out)

@app.route("/api/stock/update", methods=["POST"])
def update_stock():
    data = request.json
    if not data.get("product_id") or not data.get("quantity"):
        return jsonify({"success": False, "message": "Missing fields"}), 400

    product = products_col.find_one({"product_id": data["product_id"]})
    if not product:
        return jsonify({"success": False, "message": "Product not found"}), 404

    entry = {
        "product_id": data["product_id"],
        "quantity": int(data["quantity"]),
        "price": float(data.get("price", product["price"])),
        "expiry_date": data.get("expiry_date", None),
        "updated_at": datetime.utcnow().isoformat()
    }
    stock_col.insert_one(entry)
    return jsonify({"success": True})

@app.route("/api/stock/report/pdf", methods=["GET"])
def stock_report_pdf():
    pipeline = [
        {"$group": {
            "_id": "$product_id",
            "total_qty": {"$sum": "$quantity"},
            "latest": {"$last": "$$ROOT"}
        }},
        {"$lookup": {
            "from": "products",
            "localField": "_id",
            "foreignField": "product_id",
            "as": "product"
        }},
        {"$unwind": "$product"}
    ]
    result = list(stock_col.aggregate(pipeline))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("title", fontSize=20, alignment=TA_CENTER,
                                  fontName="Helvetica-Bold", spaceAfter=4)
    sub_style = ParagraphStyle("sub", fontSize=10, alignment=TA_CENTER,
                                textColor=colors.grey, spaceAfter=12)

    story.append(Paragraph("BILL ME", title_style))
    story.append(Paragraph(f"Stock Report — {datetime.now().strftime('%d %b %Y, %I:%M %p')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 8))

    headers = ["Product ID", "Product Name", "Type", "Qty", "Price (₹)", "Expiry Date"]
    rows = [headers]
    for r in result:
        rows.append([
            r["_id"],
            r["product"]["name"],
            r["product"]["type"],
            str(r["total_qty"]),
            f"₹{r['latest'].get('price', r['product']['price']):.2f}",
            r["latest"].get("expiry_date") or "N/A"
        ])

    t = Table(rows, colWidths=[25*mm, 50*mm, 30*mm, 15*mm, 25*mm, 30*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"stock_report_{datetime.now().strftime('%Y%m%d')}.pdf")

# ─── BILLING ────────────────────────────────────────────
@app.route("/api/bill/generate", methods=["POST"])
def generate_bill():
    data = request.json
    customer = data.get("customer", {})
    items = data.get("items", [])
    discount = float(data.get("discount", 0))

    if not items:
        return jsonify({"success": False, "message": "No items"}), 400

    subtotal = sum(i["quantity"] * i["price"] for i in items)
    discount_amt = subtotal * discount / 100
    total = subtotal - discount_amt
    gst = total * 0.18
    grand_total = total + gst

    bill_no = "B" + datetime.now().strftime("%Y%m%d%H%M%S")
    bill = {
        "bill_no": bill_no,
        "customer": customer,
        "items": items,
        "subtotal": round(subtotal, 2),
        "discount_pct": discount,
        "discount_amt": round(discount_amt, 2),
        "total": round(total, 2),
        "gst": round(gst, 2),
        "grand_total": round(grand_total, 2),
        "created_at": datetime.utcnow().isoformat()
    }
    bills_col.insert_one(bill)

    # Generate PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []

    title_s = ParagraphStyle("t", fontSize=22, alignment=TA_CENTER,
                              fontName="Helvetica-Bold", spaceAfter=2)
    sub_s = ParagraphStyle("s", fontSize=9, alignment=TA_CENTER,
                            textColor=colors.grey, spaceAfter=10)
    label_s = ParagraphStyle("l", fontSize=9, fontName="Helvetica-Bold")
    val_s = ParagraphStyle("v", fontSize=9)
    right_s = ParagraphStyle("r", fontSize=9, alignment=TA_RIGHT)

    story.append(Paragraph("BILL ME", title_s))
    story.append(Paragraph("Tax Invoice", sub_s))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 6))

    # Bill info
    info_data = [
        [Paragraph("<b>Bill No:</b>", val_s), Paragraph(bill_no, val_s),
         Paragraph("<b>Date:</b>", val_s), Paragraph(datetime.now().strftime("%d/%m/%Y %H:%M"), val_s)],
        [Paragraph("<b>Customer:</b>", val_s), Paragraph(customer.get("name", ""), val_s),
         Paragraph("<b>Mobile:</b>", val_s), Paragraph(customer.get("mobile", ""), val_s)],
    ]
    info_table = Table(info_data, colWidths=[25*mm, 65*mm, 25*mm, 65*mm])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 6))

    # Items
    item_headers = ["#", "Product", "Qty", "Unit Price", "Amount"]
    item_rows = [item_headers]
    for idx, item in enumerate(items, 1):
        item_rows.append([
            str(idx),
            item["name"],
            str(item["quantity"]),
            f"₹{item['price']:.2f}",
            f"₹{item['quantity'] * item['price']:.2f}"
        ])

    it = Table(item_rows, colWidths=[10*mm, 80*mm, 20*mm, 30*mm, 40*mm])
    it.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(it)
    story.append(Spacer(1, 8))

    # Totals
    totals = [
        ["", "Subtotal:", f"₹{subtotal:.2f}"],
        ["", f"Discount ({discount}%):", f"-₹{discount_amt:.2f}"],
        ["", "After Discount:", f"₹{total:.2f}"],
        ["", "GST (18%):", f"₹{gst:.2f}"],
        ["", "GRAND TOTAL:", f"₹{grand_total:.2f}"],
    ]
    tot_table = Table(totals, colWidths=[90*mm, 50*mm, 40*mm])
    tot_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, -1), (-1, -1), 10),
        ("LINEABOVE", (1, -1), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (1, -1), (-1, -1), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (1, -1), (-1, -1), colors.white),
    ]))
    story.append(tot_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Thank you for your purchase!", sub_s))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"bill_{bill_no}.pdf")

# ─── AVAILABLE PRODUCTS PDF ─────────────────────────────
@app.route("/api/products/report/pdf", methods=["GET"])
def products_report_pdf():
    products = list(products_col.find({}, {"_id": 0}))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    story = []

    title_s = ParagraphStyle("t", fontSize=20, alignment=TA_CENTER,
                              fontName="Helvetica-Bold", spaceAfter=4)
    sub_s = ParagraphStyle("s", fontSize=10, alignment=TA_CENTER,
                            textColor=colors.grey, spaceAfter=12)

    story.append(Paragraph("BILL ME", title_s))
    story.append(Paragraph(f"Products Report — {datetime.now().strftime('%d %b %Y')}", sub_s))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 8))

    headers = ["ID", "Name", "Type", "Manufacturer", "Price", "Expiry?"]
    rows = [headers]
    for p in products:
        rows.append([
            p.get("product_id", ""),
            p.get("name", ""),
            p.get("type", ""),
            p.get("manufacturer_name", ""),
            f"₹{p.get('price', 0):.2f}",
            "Yes" if p.get("has_expiry") else "No"
        ])

    t = Table(rows, colWidths=[20*mm, 45*mm, 30*mm, 50*mm, 22*mm, 15*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"products_report_{datetime.now().strftime('%Y%m%d')}.pdf")

# ─── TEMPLATES ──────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
