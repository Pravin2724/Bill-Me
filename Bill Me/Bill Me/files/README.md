# Bill Me — Retail Billing System

A full-stack billing application built with **Flask + MongoDB + HTML/CSS/JS**.

---

## Project Structure

```
bill_me/
├── app.py                  ← Flask backend (all routes + PDF generation)
├── setup_templates.py      ← Setup checker (run once before starting)
├── requirements.txt        ← Python dependencies
└── templates/
    └── index.html          ← Full frontend (login, billing, products, stock)
```

---

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start MongoDB
```bash
sudo systemctl start mongod          # Linux
brew services start mongodb-community # macOS
```

### 3. Verify setup
```bash
python setup_templates.py
```

### 4. Start the server
```bash
python app.py
```

### 5. Open in browser
```
http://127.0.0.1:5000
```

---

## Login Credentials

| Field    | Value      |
|----------|------------|
| Username | `bill`     |
| Password | `bill@123` |

---

## Features

| Feature | Description |
|---|---|
| **Bill Now** | Type-ahead product search, add items, view running total with GST, enter customer details, download PDF invoice |
| **Add Product** | Full manufacturer info, product type, pricing, expiry flag |
| **Update Stock** | Select product, enter quantity + optional price override + expiry date, download Stock PDF |
| **Products & Stocks** | Live table of all products with stock levels, download both PDFs |

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| POST | `/api/login` | Authenticate user |
| GET | `/api/products` | List all products |
| GET | `/api/products/search?q=` | Autocomplete search |
| POST | `/api/products/add` | Add new product |
| GET | `/api/stock` | Get stock summary |
| POST | `/api/stock/update` | Update stock entry |
| GET | `/api/stock/report/pdf` | Download stock PDF report |
| POST | `/api/bill/generate` | Generate & download invoice PDF |
| GET | `/api/products/report/pdf` | Download products PDF report |

---

## Database (MongoDB)

Database: `bill_me_db`

| Collection | Purpose |
|---|---|
| `products` | Product master data |
| `stock` | Stock entries (append-only log) |
| `bills` | Bill history |
