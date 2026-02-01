# MOBILE_V1_API_SPEC

## Base URL

- **Service B Mobile Gateway**: `/apis/mobile/v1`
- **Path convention**: mobile calls use the **exact same upstream path as Service A**.
  - Example: `GET /apis/mobile/v1/api/v1/customers` → Service B proxies to Service A `GET /api/v1/customers`

## Authentication

- Header: `Authorization: Bearer <access_token>`
- The gateway forwards the Authorization header to Service A.

## Response Envelope (JSON endpoints)

All JSON endpoints respond with:
```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

### Non-JSON endpoints (files/binary)

If the upstream returns a non-JSON response (e.g., XLSX/PDF), the gateway proxies the raw stream and **does not wrap**.

---

## Group: `/'

### GET `/apis/mobile/v1/api/v1/_meta/admin-divisions/communes`

- Upstream: `/api/v1/_meta/admin-divisions/communes`
- Source: `routers/public/admin_divisions_public.py:list_communes`
- Description: Danh sách xã/phường theo tỉnh. - province_code bắt buộc - Nếu q có: lọc accent-insensitive

**Query Parameters**
- `province_code` (int)
- `q` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`
- `province`

---

### GET `/apis/mobile/v1/api/v1/_meta/admin-divisions/provinces`

- Upstream: `/api/v1/_meta/admin-divisions/provinces`
- Source: `routers/public/admin_divisions_public.py:list_provinces`
- Description: Danh sách tỉnh/thành (từ dataset local). - Nếu q có: lọc accent-insensitive

**Query Parameters**
- `q` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`

---

### GET `/apis/mobile/v1/api/v1/catalogs/banks`

- Upstream: `/api/v1/catalogs/banks`
- Source: `routers/public/public_catalogs.py:list_banks`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[bool])
- `sort` (Optional[str])

**Dependencies**
- `page_size` (Tuple[int, int])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.dossier_types`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/catalogs/banks/{bank_id}`

- Upstream: `/api/v1/catalogs/banks/{bank_id}`
- Source: `routers/public/public_catalogs.py:get_bank`

**Path Parameters**
- `bank_id` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.dossier_types`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/dossier-types/public`

- Upstream: `/api/v1/dossier-types/public`
- Source: `routers/public/public_catalogs.py:dossier_types_public`

**Query Parameters**
- `product_type` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.dossier_types`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/health`

- Upstream: `/api/v1/health`
- Source: `routers/public/health.py:health`

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `status`

---

### GET `/apis/mobile/v1/api/v1/projects/by_code/{project_code}/dossier-types/public`

- Upstream: `/api/v1/projects/by_code/{project_code}/dossier-types/public`
- Source: `routers/public/public_catalogs.py:dossier_types_by_project_public`

**Path Parameters**
- `project_code` (str)

**Query Parameters**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `items`
- `project_code`
- `project_type`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.dossier_types`
- `v20.projects`

---

### POST `/apis/mobile/v1/api/v1/webhooks_public/provider_x`

- Upstream: `/api/v1/webhooks_public/provider_x`
- Source: `routers/public/webhooks_public.py:provider_x`

**Headers**
- `x_sig` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### GET `/apis/mobile/v1/public/registration/by-token/{token}`

- Upstream: `/public/registration/by-token/{token}`
- Source: `routers/public/registration_public.py:get_registration_by_token`
- Description: API public để Service C lấy dữ liệu phiếu đăng ký. Token được sinh ra khi ORDER DEPOSIT -> PAID (trigger DB).

**Query Parameters**
- `token` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `missing_fields`
- `ok`
- `state`
- `token`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.companies`
- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.doc_customer_company_kyc`
- `v20.doc_customer_company_kyc_history`
- `v20.doc_customer_project_documents`
- `v20.doc_customer_project_documents_history`
- *(+5 more)*

---

### GET `/apis/mobile/v1/public/registration/by-token/{token}/documents`

- Upstream: `/public/registration/by-token/{token}/documents`
- Source: `routers/public/registration_public.py:get_registration_documents_by_token`
- Description: Trả về dạng:   {     ok: true,     token: "...",     company_code: "...",     project_id: ...,     customer_id: ...,     documents: {       company_kyc: { DOC_KIND: [ {upload_id,url,created_at}, ... ] },       project_docs: { DOC_KIND: [ ... ] }     },     picks: {       cccd_front_url: "...|null",       cccd_back_url: "...|null",       application_signed_url: "...|null"     }   }  NOTE quan trọng theo schema bạn đang dùng:   - v20.doc_customer_company_kyc: latest_cccd_front_upload_id / latest_cccd_back_upload_id   - v20.doc_customer_company_kyc_history: (doc_kind, upload_id, created_at)   - v20.doc_customer_project_documents: latest_signed_form_upload_id   - v20.doc_customer_project_documents_history: (upload_id, created_at)   - v20.doc_uploads: url, created_at

**Query Parameters**
- `token` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `customer_id`
- `documents`
- `ok`
- `picks`
- `project_id`
- `token`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.companies`
- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.doc_customer_company_kyc`
- `v20.doc_customer_company_kyc_history`
- `v20.doc_customer_project_documents`
- `v20.doc_customer_project_documents_history`
- *(+5 more)*

---

### POST `/apis/mobile/v1/public/registration/by-token/{token}/documents/attach`

- Upstream: `/public/registration/by-token/{token}/documents/attach`
- Source: `routers/public/upload_public.py:attach_registration_document_by_token`
- Description: body: { doc_kind: "CCCD_FRONT|CCCD_BACK|SIGNED_FORM|APPLICATION_FORM...", upload_id: 123 }  Theo schema DB bạn cung cấp:   - Latest CCCD:       v20.doc_customer_company_kyc.latest_cccd_front_upload_id / latest_cccd_back_upload_id     + history:       v20.doc_customer_company_kyc_history(doc_kind, upload_id)    - Latest signed form:       v20.doc_customer_project_documents.latest_signed_form_upload_id     + history:       v20.doc_customer_project_documents_history(upload_id)

**Query Parameters**
- `token` (str)
- `payload` (Dict[str, Any])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `attached_to`
- `company_code`
- `customer_id`
- `doc_kind`
- `ok`
- `project_id`
- `token`
- `updated_field`
- `upload_id`
- `url`

**DB source objects referenced in code (views/tables)**

- `v20.doc_customer_company_kyc`
- `v20.doc_customer_company_kyc_history`
- `v20.doc_customer_project_documents`
- `v20.doc_customer_project_documents_history`
- `v20.doc_uploads`
- `v20.public_registration_links`

---

### POST `/apis/mobile/v1/public/uploads`

- Upstream: `/public/uploads`
- Source: `routers/public/upload_public.py:upload_public_file`
- Description: Upload file lên Cloudflare R2 (max 20MB), lưu metadata vào v20.doc_uploads, trả về upload_id + url.

**Query Parameters**
- `file` (UploadFile)
- `company_code` (Optional[str])
- `doc_kind` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `bucket`
- `mime_type`
- `object_key`
- `ok`
- `original_filename`
- `provider`
- `sha256`
- `size_bytes`
- `upload_id`
- `url`

**DB source objects referenced in code (views/tables)**

- `v20.doc_customer_company_kyc`
- `v20.doc_customer_company_kyc_history`
- `v20.doc_customer_project_documents`
- `v20.doc_customer_project_documents_history`
- `v20.doc_uploads`
- `v20.public_registration_links`

---

## Group: `/api/v1'

### GET `/apis/mobile/v1/api/v1/bank-transactions`

- Upstream: `/api/v1/bank-transactions`
- Source: `routers/business/bank_transactions.py:list_txns`

**Query Parameters**
- `q` (Optional[str])
- `from_date` (Optional[str])
- `to_date` (Optional[str])
- `status` (Optional[str])
- `account_id` (Optional[int])
- `bank_code` (Optional[str])
- `account_number` (Optional[str])
- `min_amount` (Optional[float])
- `max_amount` (Optional[float])
- `matched` (Optional[bool])
- `no_ref_only` (Optional[bool])
- `sort` (str)
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.companies`
- `v20.company_bank_accounts`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.email_outbox`
- `v20.lots`
- `v20.order_items`
- *(+1 more)*

---

### POST `/apis/mobile/v1/api/v1/bank-transactions/bulk`

- Upstream: `/api/v1/bank-transactions/bulk`
- Source: `routers/business/bank_transactions.py:import_bulk`
- Description: Nhận sao kê hàng loạt -> svc.bulk_upsert (GIỮ NGUYÊN). Sau khi upsert xong, hook best-effort:   - Quét ORDERS đã PAID kể từ lúc request bắt đầu   - Enqueue email xác nhận (dedupe theo ORDER)   - Ghi log chi tiết

**Query Parameters**
- `body` (BankBulkImportIn)

**Dependencies**
- `_checked` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.companies`
- `v20.company_bank_accounts`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.email_outbox`
- `v20.lots`
- `v20.order_items`
- *(+1 more)*

---

### POST `/apis/mobile/v1/api/v1/bank-transactions/manual`

- Upstream: `/api/v1/bank-transactions/manual`
- Source: `routers/business/bank_transactions.py:create_manual`

**Query Parameters**
- `payload` (BankTxnCreateIn)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.companies`
- `v20.company_bank_accounts`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.email_outbox`
- `v20.lots`
- `v20.order_items`
- *(+1 more)*

---

### POST `/apis/mobile/v1/api/v1/bank-transactions/search`

- Upstream: `/api/v1/bank-transactions/search`
- Source: `routers/business/bank_transactions.py:search_txns`

**Query Parameters**
- `body` (BankTxnSearchIn)

**Dependencies**
- `_checked` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.companies`
- `v20.company_bank_accounts`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.email_outbox`
- `v20.lots`
- `v20.order_items`
- *(+1 more)*

---

### GET `/apis/mobile/v1/api/v1/projects/by_code/{project_code}/payment-accounts/summary`

- Upstream: `/api/v1/projects/by_code/{project_code}/payment-accounts/summary`
- Source: `routers/business/project_payment_accounts.py:get_payment_accounts_summary_by_code`

**Query Parameters**
- `project_code` (str)
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_code}/payment-accounts`

- Upstream: `/api/v1/projects/{project_code}/payment-accounts`
- Source: `routers/business/project_payment_accounts.py:list_payment_accounts`

**Query Parameters**
- `project_code` (str)
- `company_code` (Optional[str])
- `only_active` (bool)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### POST `/apis/mobile/v1/api/v1/projects/{project_code}/payment-accounts`

- Upstream: `/api/v1/projects/{project_code}/payment-accounts`
- Source: `routers/business/project_payment_accounts.py:add_or_update_payment_account`

**Query Parameters**
- `project_code` (str)
- `payload` (ProjectPaymentAccountIn)
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### POST `/apis/mobile/v1/api/v1/projects/{project_code}/payment-accounts/{type}/deactivate`

- Upstream: `/api/v1/projects/{project_code}/payment-accounts/{type}/deactivate`
- Source: `routers/business/project_payment_accounts.py:deactivate_payment_account`

**Query Parameters**
- `project_code` (str)
- `type` (str)
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### PUT `/apis/mobile/v1/api/v1/projects/{project_id}/payment-accounts`

- Upstream: `/api/v1/projects/{project_id}/payment-accounts`
- Source: `routers/business/project_payment_accounts.py:update_payment_accounts_convenience`

**Path Parameters**
- `project_id` (int)

**Query Parameters**
- `payload` (ProjectPaymentConvenienceUpdate)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### POST `/apis/mobile/v1/api/v1/projects/{project_id}/payment-accounts/freeze`

- Upstream: `/api/v1/projects/{project_id}/payment-accounts/freeze`
- Source: `routers/business/project_payment_accounts.py:freeze_project_payment_accounts`

**Path Parameters**
- `project_id` (int)

**Query Parameters**
- `reason` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `ok`
- `project_code`
- `project_id`

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_id}/payment-accounts/freeze-status`

- Upstream: `/api/v1/projects/{project_id}/payment-accounts/freeze-status`
- Source: `routers/business/project_payment_accounts.py:get_payment_accounts_freeze_status`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `project_code`
- `project_id`

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_id}/payment-accounts/summary`

- Upstream: `/api/v1/projects/{project_id}/payment-accounts/summary`
- Source: `routers/business/project_payment_accounts.py:get_payment_accounts_summary_by_id`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.project_payment_freeze`

**Schema (likely row fields) for `v20.project_payment_freeze`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `frozen` | `boolean` | `NO` |
| `frozen_at` | `timestamp with time zone` | `NO` |
| `reason` | `text` | `YES` |

---

## Group: `/api/v1/admin'

### GET `/apis/mobile/v1/api/v1/admin/projects/{project_id}/customers`

- Upstream: `/api/v1/admin/projects/{project_id}/customers`
- Source: `routers/business/admin_customer_project.py:list_customers_by_project`
- Description: Returns rollup items. View now includes doc URLs:   - doc_cccd_front_url, doc_cccd_back_url, doc_reg_form_url (+ mime types) expose_docs=false will remove url fields from response (still keeps *_at flags).

**Query Parameters**
- `project_id` (int)
- `company` (Optional[str])
- `q` (Optional[str])
- `doc_status` (str)
- `page` (int)
- `size` (int)
- `sort` (Optional[str])
- `expose_phone` (bool)
- `expose_docs` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_adm_customer_deposit_lots_detail_20251224`
- `v20.v_adm_customer_project_rollup_20251224`

---

### GET `/apis/mobile/v1/api/v1/admin/projects/{project_id}/customers/{customer_id}`

- Upstream: `/api/v1/admin/projects/{project_id}/customers/{customer_id}`
- Source: `routers/business/admin_customer_project.py:get_customer_project_detail`

**Query Parameters**
- `project_id` (int)
- `customer_id` (int)
- `company` (Optional[str])
- `expose_phone` (bool)
- `expose_docs` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_adm_customer_deposit_lots_detail_20251224`
- `v20.v_adm_customer_project_rollup_20251224`

---

### GET `/apis/mobile/v1/api/v1/admin/projects/{project_id}/customers/{customer_id}/deposit-lots`

- Upstream: `/api/v1/admin/projects/{project_id}/customers/{customer_id}/deposit-lots`
- Source: `routers/business/admin_customer_project.py:list_customer_deposit_lots`

**Query Parameters**
- `project_id` (int)
- `customer_id` (int)
- `company` (Optional[str])
- `page` (int)
- `size` (int)
- `sort` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_adm_customer_deposit_lots_detail_20251224`
- `v20.v_adm_customer_project_rollup_20251224`

---

## Group: `/api/v1/admin/companies'

### GET `/apis/mobile/v1/api/v1/admin/companies/`

- Upstream: `/api/v1/admin/companies/`
- Source: `routers/admin/companies.py:list_companies`
- Description: Giữ nguyên API cũ: - Query: q (search), status (bool), page/size lấy từ pagination_params - Trả về: {"data": [...], "page": int, "size": int, "total": int}

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[bool])

**Dependencies**
- `page_size` (Tuple[int, int])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

---

### POST `/apis/mobile/v1/api/v1/admin/companies/`

- Upstream: `/api/v1/admin/companies/`
- Source: `routers/admin/companies.py:create_company`
- Description: Tạo company mới — giữ valid như cũ, thêm audit log.

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `id`
- `ok`

---

### POST `/apis/mobile/v1/api/v1/admin/companies/{company_code}/disable`

- Upstream: `/api/v1/admin/companies/{company_code}/disable`
- Source: `routers/admin/companies.py:disable_company`
- Description: Tắt hoạt động — giữ nguyên đáp án cũ, thêm audit (soft off).

**Query Parameters**
- `company_code` (str)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/admin/companies/{company_code}/enable`

- Upstream: `/api/v1/admin/companies/{company_code}/enable`
- Source: `routers/admin/companies.py:enable_company`
- Description: Bật hoạt động — giữ nguyên đáp án cũ, thêm audit.

**Query Parameters**
- `company_code` (str)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### PUT `/apis/mobile/v1/api/v1/admin/companies/{company_id}`

- Upstream: `/api/v1/admin/companies/{company_id}`
- Source: `routers/admin/companies.py:update_company`
- Description: Cập nhật thông tin — giữ nguyên logic cũ, thêm audit diff cơ bản.

**Path Parameters**
- `company_id` (int)

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/admin/email-outbox'

### POST `/apis/mobile/v1/api/v1/admin/email-outbox/dispatch`

- Upstream: `/api/v1/admin/email-outbox/dispatch`
- Source: `routers/admin/email_outbox.py:dispatch_once`
- Description: Worker public — không yêu cầu token. Quét bảng v20.email_outbox, gửi email PENDING và cập nhật trạng thái. Sử dụng best-effort (sẽ bỏ qua lỗi cá biệt, không raise).

**Query Parameters**
- `limit` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `stats`

**DB source objects referenced in code (views/tables)**

- `v20.email_outbox`

**Schema (likely row fields) for `v20.email_outbox`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `YES` |
| `customer_id` | `bigint` | `YES` |
| `to_email` | `text` | `NO` |
| `template_code` | `text` | `YES` |
| `subject_rendered` | `text` | `YES` |
| `body_rendered` | `text` | `YES` |
| `attachments` | `jsonb` | `YES` |
| `status` | `text` | `NO` |
| `provider` | `text` | `YES` |
| `provider_ref` | `text` | `YES` |
| `error_message` | `text` | `YES` |
| `scheduled_at` | `timestamp with time zone` | `YES` |
| `sent_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `template_key` | `text` | `YES` |
| `payload` | `jsonb` | `YES` |
| `event_type` | `text` | `YES` |
| `subject_override` | `text` | `YES` |
| `attempts` | `integer` | `YES` |
| `dedupe_key` | `text` | `YES` |
| `updated_at` | `timestamp with time zone` | `YES` |
| `last_error` | `text` | `YES` |
| `subject_used` | `text` | `YES` |
| `html_used` | `text` | `YES` |
| `next_retry_at` | `timestamp with time zone` | `YES` |
| `locked_at` | `timestamp with time zone` | `YES` |
| `locked_by` | `text` | `YES` |
| `reply_to` | `text` | `YES` |

---

### GET `/apis/mobile/v1/api/v1/admin/email-outbox/stats`

- Upstream: `/api/v1/admin/email-outbox/stats`
- Source: `routers/admin/email_outbox.py:outbox_stats`
- Description: Trả về thống kê số lượng email theo trạng thái: PENDING / SENT / ERROR / FAILED. Cho phép gọi public để giám sát nhanh (dành cho dashboard hoặc cron).

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `by_status`
- `ok`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.email_outbox`

**Schema (likely row fields) for `v20.email_outbox`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `YES` |
| `customer_id` | `bigint` | `YES` |
| `to_email` | `text` | `NO` |
| `template_code` | `text` | `YES` |
| `subject_rendered` | `text` | `YES` |
| `body_rendered` | `text` | `YES` |
| `attachments` | `jsonb` | `YES` |
| `status` | `text` | `NO` |
| `provider` | `text` | `YES` |
| `provider_ref` | `text` | `YES` |
| `error_message` | `text` | `YES` |
| `scheduled_at` | `timestamp with time zone` | `YES` |
| `sent_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `template_key` | `text` | `YES` |
| `payload` | `jsonb` | `YES` |
| `event_type` | `text` | `YES` |
| `subject_override` | `text` | `YES` |
| `attempts` | `integer` | `YES` |
| `dedupe_key` | `text` | `YES` |
| `updated_at` | `timestamp with time zone` | `YES` |
| `last_error` | `text` | `YES` |
| `subject_used` | `text` | `YES` |
| `html_used` | `text` | `YES` |
| `next_retry_at` | `timestamp with time zone` | `YES` |
| `locked_at` | `timestamp with time zone` | `YES` |
| `locked_by` | `text` | `YES` |
| `reply_to` | `text` | `YES` |

---

## Group: `/api/v1/admin/rbac'

### GET `/apis/mobile/v1/api/v1/admin/rbac/permissions`

- Upstream: `/api/v1/admin/rbac/permissions`
- Source: `routers/admin/rbac.py:list_permissions`

**Query Parameters**
- `q` (Optional[str])
- `group_code` (Optional[str])

**Dependencies**
- `page_size` (Tuple[int, int])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

---

### GET `/apis/mobile/v1/api/v1/admin/rbac/roles`

- Upstream: `/api/v1/admin/rbac/roles`
- Source: `routers/admin/rbac.py:list_roles`

**Query Parameters**
- `q` (Optional[str])

**Dependencies**
- `page_size` (Tuple[int, int])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

---

## Group: `/api/v1/admin/users'

### GET `/apis/mobile/v1/api/v1/admin/users/`

- Upstream: `/api/v1/admin/users/`
- Source: `routers/admin/users.py:list_users`

**Query Parameters**
- `q` (Optional[str])
- `role` (Optional[str])
- `company_code` (Optional[str])

**Dependencies**
- `page_size` (Tuple[int, int])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

---

### POST `/apis/mobile/v1/api/v1/admin/users/`

- Upstream: `/api/v1/admin/users/`
- Source: `routers/admin/users.py:create_user`

**Query Parameters**
- `payload` (CreateUserIn)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `id`
- `ok`
- `username`

---

### POST `/apis/mobile/v1/api/v1/admin/users/{user_id}/disable`

- Upstream: `/api/v1/admin/users/{user_id}/disable`
- Source: `routers/admin/users.py:disable_user`

**Path Parameters**
- `user_id` (int)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/admin/users/{user_id}/enable`

- Upstream: `/api/v1/admin/users/{user_id}/enable`
- Source: `routers/admin/users.py:enable_user`

**Path Parameters**
- `user_id` (int)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/admin/users/{user_id}/force_set_password`

- Upstream: `/api/v1/admin/users/{user_id}/force_set_password`
- Source: `routers/admin/users.py:force_set_password`

**Query Parameters**
- `user_id` (int)
- `payload` (dict)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/admin/whitelist'

### GET `/apis/mobile/v1/api/v1/admin/whitelist/`

- Upstream: `/api/v1/admin/whitelist/`
- Source: `routers/admin/whitelist.py:list_whitelist`

**Query Parameters**
- `q` (Optional[str])

**Dependencies**
- `page_size` (Tuple[int, int])
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

---

### POST `/apis/mobile/v1/api/v1/admin/whitelist/`

- Upstream: `/api/v1/admin/whitelist/`
- Source: `routers/admin/whitelist.py:add_ip`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (str)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `id`
- `ok`

---

### DELETE `/apis/mobile/v1/api/v1/admin/whitelist/{ip_id}`

- Upstream: `/api/v1/admin/whitelist/{ip_id}`
- Source: `routers/admin/whitelist.py:remove_ip`

**Path Parameters**
- `ip_id` (int)

**Dependencies**
- `company_code` (str)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/announcements'

### GET `/apis/mobile/v1/api/v1/announcements/`

- Upstream: `/api/v1/announcements/`
- Source: `routers/business/announcements.py:list_announcements_admin`

**Query Parameters**
- `status` (Optional[str])
- `q` (Optional[str])
- `company_code` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/announcements/`

- Upstream: `/api/v1/announcements/`
- Source: `routers/business/announcements.py:create_announcement`

**Query Parameters**
- `payload` (Dict[str, Any])
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

### DELETE `/apis/mobile/v1/api/v1/announcements/{ann_id}`

- Upstream: `/api/v1/announcements/{ann_id}`
- Source: `routers/business/announcements.py:delete_announcement_soft`

**Path Parameters**
- `ann_id` (int)

**Query Parameters**
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/announcements/{ann_id}`

- Upstream: `/api/v1/announcements/{ann_id}`
- Source: `routers/business/announcements.py:get_announcement_admin`

**Path Parameters**
- `ann_id` (int)

**Query Parameters**
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/announcements/{ann_id}`

- Upstream: `/api/v1/announcements/{ann_id}`
- Source: `routers/business/announcements.py:update_announcement`

**Path Parameters**
- `ann_id` (int)

**Query Parameters**
- `payload` (Dict[str, Any])
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

### DELETE `/apis/mobile/v1/api/v1/announcements/{ann_id}/hard`

- Upstream: `/api/v1/announcements/{ann_id}/hard`
- Source: `routers/business/announcements.py:delete_announcement_hard`

**Path Parameters**
- `ann_id` (int)

**Query Parameters**
- `company_code` (str)

**Dependencies**
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

## Group: `/api/v1/auction-counting'

### GET `/apis/mobile/v1/api/v1/auction-counting/display/events`

- Upstream: `/api/v1/auction-counting/display/events`
- Source: `routers/business/auction_counting_display.py:display_events_sse`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-counting/display/snapshot`

- Upstream: `/api/v1/auction-counting/display/snapshot`
- Source: `routers/business/auction_counting_display.py:display_snapshot`

**Query Parameters**
- `project_id` (int)
- `session_id` (Optional[int])

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `project`
- `session`
- `summary`
- `tied`
- `winners`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-counting/projects/{project_id}/lots`

- Upstream: `/api/v1/auction-counting/projects/{project_id}/lots`
- Source: `routers/business/auction_counting_display.py:list_project_lots_with_counting`

**Path Parameters**
- `project_id` (int)

**Query Parameters**
- `session_id` (Optional[int])
- `q` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`
- `page`
- `project`
- `session`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-counting/projects/{project_id}/lots/{lot_code}/eligible-customers`

- Upstream: `/api/v1/auction-counting/projects/{project_id}/lots/{lot_code}/eligible-customers`
- Source: `routers/business/auction_counting_display.py:list_eligible_customers_for_counting`

**Path Parameters**
- `project_id` (int)
- `lot_code` (str)

**Query Parameters**
- `limit` (int)
- `include_unpaid` (bool)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `lot_code`
- `ok`
- `project_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-counting/projects/{project_id}/sessions/current`

- Upstream: `/api/v1/auction-counting/projects/{project_id}/sessions/current`
- Source: `routers/business/auction_counting_display.py:get_current_counting_session`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `session`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### POST `/apis/mobile/v1/api/v1/auction-counting/projects/{project_id}/sessions/start`

- Upstream: `/api/v1/auction-counting/projects/{project_id}/sessions/start`
- Source: `routers/business/auction_counting_display.py:start_counting_session`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `note`
- `ok`
- `session`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### POST `/apis/mobile/v1/api/v1/auction-counting/sessions/{session_id}/close`

- Upstream: `/api/v1/auction-counting/sessions/{session_id}/close`
- Source: `routers/business/auction_counting_display.py:close_counting_session`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `session`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

### PUT `/apis/mobile/v1/api/v1/auction-counting/sessions/{session_id}/lots/{lot_code}`

- Upstream: `/api/v1/auction-counting/sessions/{session_id}/lots/{lot_code}`
- Source: `routers/business/auction_counting_display.py:upsert_counting_for_lot`

**Path Parameters**
- `session_id` (int)
- `lot_code` (str)

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `event`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.projects`

---

## Group: `/api/v1/auction-counting/print'

### GET `/apis/mobile/v1/api/v1/auction-counting/print/sessions/{session_id}/tied-print-pairs`

- Upstream: `/api/v1/auction-counting/print/sessions/{session_id}/tied-print-pairs`
- Source: `routers/business/auction_counting_print.py:get_tied_print_pairs`
- Description: Trả về danh sách các cặp (lot_id, customer_id) cho các lô đang TIED trong 1 counting session.  sort_type:   - lot_customer: lot_id ASC, customer_id ASC (default)   - customer_lot: customer_id ASC, lot_id ASC

**Path Parameters**
- `session_id` (int)

**Query Parameters**
- `only_lot_id` (Optional[int])
- `sort_type` (Literal['lot_customer', 'customer_lot'])

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `meta`
- `ok`
- `pairs`
- `project`
- `session_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_counting_lots`
- `v20.auction_counting_sessions`
- `v20.lots`
- `v20.projects`

---

## Group: `/api/v1/auction-results'

### GET `/apis/mobile/v1/api/v1/auction-results/customers/search`

- Upstream: `/api/v1/auction-results/customers/search`
- Source: `routers/business/auction_results.py:search_customers_for_winner_picker`

**Query Parameters**
- `q` (str)
- `limit` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### POST `/apis/mobile/v1/api/v1/auction-results/projects/{project_id}/bulk-upsert`

- Upstream: `/api/v1/auction-results/projects/{project_id}/bulk-upsert`
- Source: `routers/business/auction_results.py:bulk_upsert_auction_results`

**Path Parameters**
- `project_id` (int)

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `errors`
- `finalized_by`
- `inserted`
- `ok`
- `updated`

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-results/projects/{project_id}/eligible-lots`

- Upstream: `/api/v1/auction-results/projects/{project_id}/eligible-lots`
- Source: `routers/business/auction_results.py:list_project_eligible_lots`

**Path Parameters**
- `project_id` (int)

**Query Parameters**
- `q` (Optional[str])
- `include_unpaid` (bool)
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `include_unpaid`
- `page`
- `project`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-results/projects/{project_id}/export-winners-xlsx`

- Upstream: `/api/v1/auction-results/projects/{project_id}/export-winners-xlsx`
- Source: `routers/business/auction_results.py:export_winners_xlsx`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-results/projects/{project_id}/lots`

- Upstream: `/api/v1/auction-results/projects/{project_id}/lots`
- Source: `routers/business/auction_results.py:list_project_lots_with_results`

**Path Parameters**
- `project_id` (int)

**Query Parameters**
- `q` (Optional[str])
- `result_status` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `project`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### PUT `/apis/mobile/v1/api/v1/auction-results/projects/{project_id}/lots/{lot_code}`

- Upstream: `/api/v1/auction-results/projects/{project_id}/lots/{lot_code}`
- Source: `routers/business/auction_results.py:upsert_lot_auction_result`

**Path Parameters**
- `project_id` (int)
- `lot_code` (str)

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `finalized_by`
- `is_lucky_draw`
- `lot_code`
- `ok`
- `project_id`
- `result_status`

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-results/projects/{project_id}/lots/{lot_code}/eligible-customers`

- Upstream: `/api/v1/auction-results/projects/{project_id}/lots/{lot_code}/eligible-customers`
- Source: `routers/business/auction_results.py:list_eligible_customers_for_lot`

**Path Parameters**
- `project_id` (int)
- `lot_code` (str)

**Query Parameters**
- `limit` (int)
- `include_unpaid` (bool)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `lot_code`
- `project_id`

**DB source objects referenced in code (views/tables)**

- `v20.customer_lot_deposits`
- `v20.customers`
- `v20.lot_registrations`
- `v20.lots`
- `v20.project_lot_auction_results`
- `v20.projects`

---

## Group: `/api/v1/auction-results/print'

### GET `/apis/mobile/v1/api/v1/auction-results/print/projects/{project_id}`

- Upstream: `/api/v1/auction-results/print/projects/{project_id}`
- Source: `routers/business/auction_printing.py:get_print_data_project_winners`

**Path Parameters**
- `project_id` (int)

**Query Parameters**
- `only_lucky_draw` (bool)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`
- `project`
- `total_winners`

**DB source objects referenced in code (views/tables)**

- `v20.companies`
- `v20.project_lot_auction_results`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction-results/print/projects/{project_id}/lots/{lot_code}`

- Upstream: `/api/v1/auction-results/print/projects/{project_id}/lots/{lot_code}`
- Source: `routers/business/auction_printing.py:get_print_data_one_lot_winner`

**Path Parameters**
- `project_id` (int)
- `lot_code` (str)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `project`
- `winner`

**DB source objects referenced in code (views/tables)**

- `v20.companies`
- `v20.project_lot_auction_results`
- `v20.projects`

---

## Group: `/api/v1/auction-sessions'

### GET `/apis/mobile/v1/api/v1/auction-sessions/projects/{project_id}/active`

- Upstream: `/api/v1/auction-sessions/projects/{project_id}/active`
- Source: `routers/business/auction_sessions.py:get_active_session_for_project`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `candidates`
- `has_active`
- `primary_session`
- `project_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/round-lots/{round_lot_id}/decide`

- Upstream: `/api/v1/auction-sessions/round-lots/{round_lot_id}/decide`
- Source: `routers/business/auction_sessions.py:decide_round_lot`

**Path Parameters**
- `round_lot_id` (int)

**JSON Body**
- `payload` (DecideIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/round-lots/{round_lot_id}/lock`

- Upstream: `/api/v1/auction-sessions/round-lots/{round_lot_id}/lock`
- Source: `routers/business/auction_sessions.py:lock_round_lot`

**Path Parameters**
- `round_lot_id` (int)

**JSON Body**
- `payload` (LockIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/round-lots/{round_lot_id}/unlock`

- Upstream: `/api/v1/auction-sessions/round-lots/{round_lot_id}/unlock`
- Source: `routers/business/auction_sessions.py:unlock_round_lot`

**Path Parameters**
- `round_lot_id` (int)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions`

- Upstream: `/api/v1/auction-sessions/sessions`
- Source: `routers/business/auction_sessions.py:list_sessions`

**Query Parameters**
- `project_id` (Optional[int])
- `status` (Optional[SessionStatus])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions`

- Upstream: `/api/v1/auction-sessions/sessions`
- Source: `routers/business/auction_sessions.py:create_session`

**JSON Body**
- `payload` (SessionCreateIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions/start`

- Upstream: `/api/v1/auction-sessions/sessions/start`
- Source: `routers/business/auction_sessions.py:start_session`

**JSON Body**
- `payload` (SessionStartIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `project`
- `round_id`
- `round_no`
- `session_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### DELETE `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}`
- Source: `routers/business/auction_sessions.py:delete_session`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `deleted_session_id`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}`
- Source: `routers/business/auction_sessions.py:get_session`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### PUT `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}`
- Source: `routers/business/auction_sessions.py:update_session`

**Path Parameters**
- `session_id` (int)

**JSON Body**
- `payload` (SessionUpdateIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/backfill-stt`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/backfill-stt`
- Source: `routers/business/auction_sessions.py:backfill_stt`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `session_id`
- `updated_rows`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/current`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/current`
- Source: `routers/business/auction_sessions.py:get_current_round`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `current_round_no`
- `ok`
- `session_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/delete-check`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/delete-check`
- Source: `routers/business/auction_sessions.py:delete_session_check`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `can_delete`
- `ok`
- `reasons`
- `session_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/lock`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/lock`
- Source: `routers/business/auction_sessions.py:lock_session`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/results`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/results`
- Source: `routers/business/auction_sessions.py:list_session_results`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/rounds`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/rounds`
- Source: `routers/business/auction_sessions.py:list_rounds`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/rounds/next`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/rounds/next`
- Source: `routers/business/auction_sessions.py:create_next_round`

**Path Parameters**
- `session_id` (int)

**JSON Body**
- `payload` (NextRoundIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `created_lot_count`
- `created_round_id`
- `created_round_no`
- `from_round_no`
- `ok`
- `session_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### DELETE `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}`
- Source: `routers/business/auction_sessions.py:delete_last_round`

**Path Parameters**
- `session_id` (int)
- `round_no` (int)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `current_round_no`
- `deleted`
- `deleted_round_no`
- `ok`
- `rolled_back_lot_results`
- `session_id`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/delete-check`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/delete-check`
- Source: `routers/business/auction_sessions.py:delete_round_check`

**Path Parameters**
- `session_id` (int)
- `round_no` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `can_delete`
- `max_round_no`
- `ok`
- `reasons`
- `round_no`
- `session_id`
- `will_delete`
- `will_rollback_lot_results`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui`
- Source: `routers/business/auction_sessions.py:get_round_ui`

**Path Parameters**
- `session_id` (int)
- `round_no` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `lots`
- `meta`
- `ok`
- `round`
- `session`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/status`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/status`
- Source: `routers/business/auction_sessions.py:update_session_status`

**Path Parameters**
- `session_id` (int)

**JSON Body**
- `payload` (SessionUpdateStatusIn)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/sessions/{session_id}/unlock`

- Upstream: `/api/v1/auction-sessions/sessions/{session_id}/unlock`
- Source: `routers/business/auction_sessions.py:unlock_session`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_code` (str)
- `auth_user` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.banks`
- `v20.customer_bank_accounts`
- *(+4 more)*

---

## Group: `/api/v1/auction-sessions/display'

### GET `/apis/mobile/v1/api/v1/auction-sessions/display/sessions/{session_id}`

- Upstream: `/api/v1/auction-sessions/display/sessions/{session_id}`
- Source: `routers/business/auction_session_display.py:get_display_payload`

**Path Parameters**
- `session_id` (int)

**Query Parameters**
- `round_no` (Optional[int])

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `by_customer`
- `by_lot`
- `by_status`
- `context`
- `recent_checked_lots`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_round_lot_next_participants`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

## Group: `/api/v1/auction-sessions/print'

### GET `/apis/mobile/v1/api/v1/auction-sessions/print/round-lots/{round_lot_id}/winner`

- Upstream: `/api/v1/auction-sessions/print/round-lots/{round_lot_id}/winner`
- Source: `routers/business/auction_session_winner_printing.py:get_print_data_by_round_lot_id`

**Path Parameters**
- `round_lot_id` (int)

**Dependencies**
- `company_dep` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `project`
- `round`
- `session`
- `winner`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/print/sessions/{session_id}/customers/{customer_id}/winners`

- Upstream: `/api/v1/auction-sessions/print/sessions/{session_id}/customers/{customer_id}/winners`
- Source: `routers/business/auction_session_winner_printing.py:get_print_data_customer_winners_in_session`

**Path Parameters**
- `session_id` (int)
- `customer_id` (int)

**Dependencies**
- `company_dep` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `customer`
- `items`
- `project`
- `session`
- `total_winners`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/lots/{lot_code}`

- Upstream: `/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/lots/{lot_code}`
- Source: `routers/business/auction_session_winner_printing.py:get_print_data_one_lot_winner_in_round`

**Path Parameters**
- `session_id` (int)
- `round_no` (int)
- `lot_code` (str)

**Dependencies**
- `company_dep` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `project`
- `round`
- `session`
- `winner`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/winners`

- Upstream: `/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/winners`
- Source: `routers/business/auction_session_winner_printing.py:get_print_data_round_winners`

**Path Parameters**
- `session_id` (int)
- `round_no` (int)

**Dependencies**
- `company_dep` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`
- `project`
- `round`
- `session`
- `total_winners`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

### GET `/apis/mobile/v1/api/v1/auction-sessions/print/sessions/{session_id}/winners`

- Upstream: `/api/v1/auction-sessions/print/sessions/{session_id}/winners`
- Source: `routers/business/auction_session_winner_printing.py:get_print_data_session_winners`

**Path Parameters**
- `session_id` (int)

**Dependencies**
- `company_dep` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`
- `project`
- `session`
- `total_winners`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

### POST `/apis/mobile/v1/api/v1/auction-sessions/print/winners/selected`

- Upstream: `/api/v1/auction-sessions/print/winners/selected`
- Source: `routers/business/auction_session_winner_printing.py:get_print_data_selected_winners`

**JSON Body**
- `payload` (SelectedWinnerPayload)

**Dependencies**
- `company_dep` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `groups`
- `total_groups`
- `total_items`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_lot_results`
- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.companies`
- `v20.customers`
- `v20.lots`
- *(+1 more)*

---

## Group: `/api/v1/auction/eligibility-exclusions'

### GET `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/`

- Upstream: `/api/v1/auction/eligibility-exclusions/`
- Source: `routers/business/auction_eligibility_exclusions.py:list_exclusions`

**Query Parameters**
- `project_id` (Optional[int])
- `customer_id` (Optional[int])
- `lot_id` (Optional[int])
- `status` (Optional[str])
- `page` (int)
- `size` (int)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

### GET `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/auto-lots`

- Upstream: `/api/v1/auction/eligibility-exclusions/auto-lots`
- Source: `routers/business/auction_eligibility_exclusions.py:get_auto_lots`

**Query Parameters**
- `project_id` (int)
- `customer_id` (int)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

### POST `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/clear-customer`

- Upstream: `/api/v1/auction/eligibility-exclusions/clear-customer`
- Source: `routers/business/auction_eligibility_exclusions.py:clear_customer_all_lots`

**Query Parameters**
- `company_code_q` (Optional[str])

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

### POST `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/clear-lot`

- Upstream: `/api/v1/auction/eligibility-exclusions/clear-lot`
- Source: `routers/business/auction_eligibility_exclusions.py:clear_one_lot`

**Query Parameters**
- `company_code_q` (Optional[str])

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

### POST `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/exclude-customer`

- Upstream: `/api/v1/auction/eligibility-exclusions/exclude-customer`
- Source: `routers/business/auction_eligibility_exclusions.py:exclude_customer_all_lots`

**Query Parameters**
- `company_code_q` (Optional[str])

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

### POST `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/exclude-lot`

- Upstream: `/api/v1/auction/eligibility-exclusions/exclude-lot`
- Source: `routers/business/auction_eligibility_exclusions.py:exclude_one_lot`

**Query Parameters**
- `company_code_q` (Optional[str])

**JSON Body**
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

### GET `/apis/mobile/v1/api/v1/auction/eligibility-exclusions/summary`

- Upstream: `/api/v1/auction/eligibility-exclusions/summary`
- Source: `routers/business/auction_eligibility_exclusions.py:get_customer_summary`

**Query Parameters**
- `project_id` (int)
- `customer_id` (int)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`

**DB source objects referenced in code (views/tables)**

- `v20.auction_eligibility_exclusions`
- `v20.v_report_bid_ticket_candidates_auto`

---

## Group: `/api/v1/auction/refunds'

### GET `/apis/mobile/v1/api/v1/auction/refunds/`

- Upstream: `/api/v1/auction/refunds/`
- Source: `routers/business/deposit_refunds.py:list_refund_candidates`
- Description: Read from v20.deposit_refund_candidates (snapshot). Adds:   - total_amount_vnd = SUM(refund_amount_vnd) per current filter   - trust fields for UI highlight   - filter score_level: ALL|LOW|MEDIUM|HIGH

**Query Parameters**
- `project_id` (Optional[int])
- `eligible` (EligibleMode)
- `score_level` (str)
- `q` (str)
- `page` (int)
- `size` (int)

**Dependencies**
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `eligible`
- `ok`
- `page`
- `score_level`
- `size`
- `total`
- `total_amount_vnd`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_payer_accounts`
- `v20.deposit_refund_candidates`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction/refunds/export.xlsx`

- Upstream: `/api/v1/auction/refunds/export.xlsx`
- Source: `routers/business/deposit_refunds.py:export_refunds_xlsx`
- Description: Download XLSX list for ONE project. Default exports ELIGIBLE = "Phải hoàn".  Added:   - Bank BIN (from v20.banks.bin)   - Bank Name (from v20.banks.name)   - Trust level (from v20.customer_payer_accounts)  Formatting:   - Header: bold + light gray fill   - Freeze row 1   - Wrap text for Transfer Content   - Money format "#,##0"  NOTE: Removed columns: "Excluded Reason" and "Updated at"

**Query Parameters**
- `project_id` (Optional[int])
- `eligible` (EligibleMode)
- `score_level` (str)

**Dependencies**
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_payer_accounts`
- `v20.deposit_refund_candidates`
- `v20.projects`

---

### POST `/apis/mobile/v1/api/v1/auction/refunds/rebuild`

- Upstream: `/api/v1/auction/refunds/rebuild`
- Source: `routers/business/deposit_refunds.py:rebuild_refund_candidates`
- Description: Force rebuild snapshot for ONE project_id. - Calls DB fn: v20.fn_rebuild_deposit_refund_candidates_for_project(project_id)

**Query Parameters**
- `project_id` (Optional[int])

**Dependencies**
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `processed_orders`
- `project_id`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_payer_accounts`
- `v20.deposit_refund_candidates`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/auction/refunds/{candidate_id}/detail`

- Upstream: `/api/v1/auction/refunds/{candidate_id}/detail`
- Source: `routers/business/deposit_refunds.py:refund_candidate_detail`

**Path Parameters**
- `candidate_id` (int)

**Dependencies**
- `me` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `accounts_used`
- `candidate`
- `current_refund_account`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_payer_accounts`
- `v20.deposit_refund_candidates`
- `v20.projects`

---

## Group: `/api/v1/balances'

### GET `/apis/mobile/v1/api/v1/balances/customer-dossier`

- Upstream: `/api/v1/balances/customer-dossier`
- Source: `routers/business/balances.py:customer_dossier_balances`

**Query Parameters**
- `customer_id` (Optional[int])
- `project_id` (Optional[int])

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_customer_dossier_balances`

**Schema (likely row fields) for `v20.v_customer_dossier_balances`**

| field | type | nullable |
|---|---|---|
| `company_code` | `text` | `YES` |
| `project_id` | `bigint` | `YES` |
| `customer_id` | `bigint` | `YES` |
| `dossier_type_id` | `bigint` | `YES` |
| `purchased_qty` | `bigint` | `YES` |
| `used_qty` | `bigint` | `YES` |
| `available_qty` | `bigint` | `YES` |
| `last_paid_at` | `timestamp with time zone` | `YES` |

---

## Group: `/api/v1/business/documents'

### GET `/apis/mobile/v1/api/v1/business/documents/auction/registration`

- Upstream: `/api/v1/business/documents/auction/registration`
- Source: `routers/business/auction_docs.py:get_auction_registration_doc`
- Description: Lấy dữ liệu dựng 'Đơn đăng ký tham gia đấu giá' cho 1 khách: - company_code lấy từ company_scope (token) - Không nhận company_code từ client  URL:   GET /api/v1/business/documents/auction/registration?project_code=...&cccd=...

**Query Parameters**
- `project_code` (str)
- `cccd` (str)

**Dependencies**
- `company_scope` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

## Group: `/api/v1/company'

### GET `/apis/mobile/v1/api/v1/company/profile`

- Upstream: `/api/v1/company/profile`
- Source: `routers/business/company_profile.py:get_company_profile`
- Description: - Người trong công ty: lấy theo scope. - SUPER_ADMIN: có thể truyền ?company_code=... để xem công ty bất kỳ.

**Query Parameters**
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### PUT `/apis/mobile/v1/api/v1/company/profile`

- Upstream: `/api/v1/company/profile`
- Source: `routers/business/company_profile.py:update_company_profile`
- Description: - COMPANY_ADMIN: cập nhật công ty của chính mình (company_scope). - SUPER_ADMIN: có thể cập nhật công ty khác bằng ?company_code=...

**Query Parameters**
- `payload` (Dict[str, Any])
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

---

## Group: `/api/v1/company_bank_accounts'

### GET `/apis/mobile/v1/api/v1/company_bank_accounts/`

- Upstream: `/api/v1/company_bank_accounts/`
- Source: `routers/business/company_bank_accounts.py:list_company_bank_accounts`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[bool])
- `company_code_q` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/company_bank_accounts/`

- Upstream: `/api/v1/company_bank_accounts/`
- Source: `routers/business/company_bank_accounts.py:create_company_bank_account`

**Query Parameters**
- `payload` (Dict[str, Any])
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### DELETE `/apis/mobile/v1/api/v1/company_bank_accounts/{acc_id}`

- Upstream: `/api/v1/company_bank_accounts/{acc_id}`
- Source: `routers/business/company_bank_accounts.py:delete_company_bank_account`

**Query Parameters**
- `acc_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/company_bank_accounts/{acc_id}`

- Upstream: `/api/v1/company_bank_accounts/{acc_id}`
- Source: `routers/business/company_bank_accounts.py:get_company_bank_account`

**Path Parameters**
- `acc_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/company_bank_accounts/{acc_id}`

- Upstream: `/api/v1/company_bank_accounts/{acc_id}`
- Source: `routers/business/company_bank_accounts.py:update_company_bank_account`

**Path Parameters**
- `acc_id` (int)

**Query Parameters**
- `payload` (Dict[str, Any] | None)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/company_bank_accounts/{acc_id}/disable`

- Upstream: `/api/v1/company_bank_accounts/{acc_id}/disable`
- Source: `routers/business/company_bank_accounts.py:disable_company_bank_account`

**Query Parameters**
- `acc_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/company_bank_accounts/{acc_id}/enable`

- Upstream: `/api/v1/company_bank_accounts/{acc_id}/enable`
- Source: `routers/business/company_bank_accounts.py:enable_company_bank_account`

**Query Parameters**
- `acc_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

## Group: `/api/v1/customers'

### GET `/apis/mobile/v1/api/v1/customers/`

- Upstream: `/api/v1/customers/`
- Source: `routers/business/customers.py:list_customers`
- Description: Tìm kiếm ưu tiên theo: Họ tên → CCCD → SĐT → Email → Địa chỉ - Họ tên/Địa chỉ: so sánh unaccent + lower ở CẢ 2 vế - CCCD/SĐT/Email: so sánh lower (riêng phone, cccd có thể là số nhưng vẫn LIKE) Phân trang tối đa 200/trang.

**Query Parameters**
- `q` (Optional[str])
- `company_code` (Optional[str])

**Dependencies**
- `page_size` (Tuple[int, int])
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`

---

### POST `/apis/mobile/v1/api/v1/customers/`

- Upstream: `/api/v1/customers/`
- Source: `routers/business/customers.py:create_customer`

**Query Parameters**
- `payload` (CustomerCreate)
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`

---

### GET `/apis/mobile/v1/api/v1/customers/__diag2`

- Upstream: `/api/v1/customers/__diag2`
- Source: `routers/business/customers.py:diag_customers2`
- Description: Chẩn đoán nhanh xem lỗi nằm ở DB hay mapping ORM: - Kiểm tra search_path của session hiện tại - Kiểm tra bảng có tồn tại - Đếm bản ghi bằng RAW SQL (không qua ORM) - Thử ORM an toàn chỉ chọn cột id (tránh cột mixin) - Thử ORM full row (nếu lỗi -> nhiều khả năng model có cột không tồn tại)

**Query Parameters**
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`

---

### GET `/apis/mobile/v1/api/v1/customers/{customer_id}`

- Upstream: `/api/v1/customers/{customer_id}`
- Source: `routers/business/customers.py:get_customer`

**Path Parameters**
- `customer_id` (int)

**Query Parameters**
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`

---

### PUT `/apis/mobile/v1/api/v1/customers/{customer_id}`

- Upstream: `/api/v1/customers/{customer_id}`
- Source: `routers/business/customers.py:update_customer`
- Description: Cho phép ADMIN chỉnh sửa toàn bộ thông tin khách hàng (kể cả CCCD). - Kiểm tra trùng CCCD trong cùng company_code (trừ chính bản ghi này) - Ghi log audit đầy đủ old/new

**Query Parameters**
- `customer_id` (int)
- `payload` (CustomerUpdate)
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`

---

### POST `/apis/mobile/v1/api/v1/customers/{customer_id}/bank_accounts`

- Upstream: `/api/v1/customers/{customer_id}/bank_accounts`
- Source: `routers/business/customers.py:add_customer_bank_account`
- Description: Thêm tài khoản ngân hàng cho khách hàng: - Bắt buộc: bank_code, account_number - Tùy chọn: account_name, is_preferred - Ràng buộc: trong 1 customer, (bank_code, account_number) phải unique

**Query Parameters**
- `customer_id` (int)
- `payload` (Dict[str, Any])
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`

---

## Group: `/api/v1/dashboard'

### GET `/apis/mobile/v1/api/v1/dashboard/dossier/by-type`

- Upstream: `/api/v1/dashboard/dossier/by-type`
- Source: `routers/business/dashboard_api.py:dashboard_dossier_by_type`

**Query Parameters**
- `company` (Optional[str])
- `project` (Optional[str])
- `sort` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

### GET `/apis/mobile/v1/api/v1/dashboard/kpi`

- Upstream: `/api/v1/dashboard/kpi`
- Source: `routers/business/dashboard_api.py:dashboard_kpi`

**Query Parameters**
- `company` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `item`

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

### GET `/apis/mobile/v1/api/v1/dashboard/kpi/by-project`

- Upstream: `/api/v1/dashboard/kpi/by-project`
- Source: `routers/business/dashboard_api.py:dashboard_kpi_by_project`

**Query Parameters**
- `company` (Optional[str])
- `project` (Optional[str])
- `sort` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

### GET `/apis/mobile/v1/api/v1/dashboard/projects/rollup`

- Upstream: `/api/v1/dashboard/projects/rollup`
- Source: `routers/business/dashboard_api.py:dashboard_project_rollup`

**Query Parameters**
- `company` (Optional[str])
- `project` (Optional[str])
- `sort` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

### GET `/apis/mobile/v1/api/v1/dashboard/recent-actions`

- Upstream: `/api/v1/dashboard/recent-actions`
- Source: `routers/business/dashboard_api.py:dashboard_recent_actions`

**Query Parameters**
- `company` (Optional[str])
- `limit` (int)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `rows`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

### GET `/apis/mobile/v1/api/v1/dashboard/revenue/daily`

- Upstream: `/api/v1/dashboard/revenue/daily`
- Source: `routers/business/dashboard_api.py:dashboard_daily_revenue`

**Query Parameters**
- `company` (Optional[str])
- `project` (Optional[str])
- `date_from` (Optional[str])
- `date_to` (Optional[str])
- `sort` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

### GET `/apis/mobile/v1/api/v1/dashboard/top-customers`

- Upstream: `/api/v1/dashboard/top-customers`
- Source: `routers/business/dashboard_api.py:dashboard_top_customers`

**Query Parameters**
- `company` (Optional[str])
- `project` (Optional[str])
- `sort` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.v_dashboard_daily_revenue`
- `v20.v_dashboard_dossier_by_type`
- `v20.v_dashboard_kpi`
- `v20.v_dashboard_kpi_by_project`
- `v20.v_dashboard_project_rollup`
- `v20.v_dashboard_recent_actions`
- `v20.v_dashboard_top_customers`

---

## Group: `/api/v1/dossier-orders'

### GET `/apis/mobile/v1/api/v1/dossier-orders/`

- Upstream: `/api/v1/dossier-orders/`
- Source: `routers/business/dossier_orders.py:list_dossier_orders`
- Description: Danh sách đơn **mua hồ sơ** (APPLICATION) theo công ty / (tuỳ chọn) dự án / khách hàng / trạng thái. Trả thêm:   - payment_state: UNPAID|PARTIAL|PAID   - purchased_qty, used_qty, available_qty

**Query Parameters**
- `status` (Optional[str])
- `customer_id` (Optional[int])
- `project_id` (Optional[int])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### GET `/apis/mobile/v1/api/v1/dossier-orders/summary`

- Upstream: `/api/v1/dossier-orders/summary`
- Source: `routers/business/dossier_orders.py:dossier_orders_summary`

**Query Parameters**
- `project_id` (int | None)
- `customer_id` (int | None)
- `page` (int)
- `size` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

---

### GET `/apis/mobile/v1/api/v1/dossier-orders/{order_id}`

- Upstream: `/api/v1/dossier-orders/{order_id}`
- Source: `routers/business/dossier_orders.py:get_dossier_order_detail`
- Description: Chi tiết một đơn **mua hồ sơ** (APPLICATION) + các item.

**Path Parameters**
- `order_id` (int)

**Dependencies**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

## Group: `/api/v1/emails'

### POST `/apis/mobile/v1/api/v1/emails/send`

- Upstream: `/api/v1/emails/send`
- Source: `routers/business/emails.py:api_send_email`

**Query Parameters**
- `payload` (EmailSend)

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### POST `/apis/mobile/v1/api/v1/emails/send-with-attachments`

- Upstream: `/api/v1/emails/send-with-attachments`
- Source: `routers/business/emails.py:api_send_email_with_attachments`

**Query Parameters**
- `payload` (EmailSendWithAtt)

**Dependencies**
- `company_scope` (Optional[str])
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

## Group: `/api/v1/invoices'

### GET `/apis/mobile/v1/api/v1/invoices/`

- Upstream: `/api/v1/invoices/`
- Source: `routers/business/invoices.py:list_invoices`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### POST `/apis/mobile/v1/api/v1/invoices/`

- Upstream: `/api/v1/invoices/`
- Source: `routers/business/invoices.py:create_invoice`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `id`
- `ok`

---

### POST `/apis/mobile/v1/api/v1/invoices/{invoice_id}/cancel`

- Upstream: `/api/v1/invoices/{invoice_id}/cancel`
- Source: `routers/business/invoices.py:cancel_invoice`

**Query Parameters**
- `invoice_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/lots'

### GET `/apis/mobile/v1/api/v1/lots/`

- Upstream: `/api/v1/lots/`
- Source: `routers/business/lots.py:list_lots`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[str])
- `project_code` (Optional[str])
- `company_code` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.order_items`
- `v20.orders`

---

### POST `/apis/mobile/v1/api/v1/lots/`

- Upstream: `/api/v1/lots/`
- Source: `routers/business/lots.py:create_lot`

**Query Parameters**
- `payload` (Dict[str, Any])
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.order_items`
- `v20.orders`

---

### PATCH `/apis/mobile/v1/api/v1/lots/{lot_id}`

- Upstream: `/api/v1/lots/{lot_id}`
- Source: `routers/business/lots.py:update_lot`

**Query Parameters**
- `lot_id` (int)
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.order_items`
- `v20.orders`

---

### GET `/apis/mobile/v1/api/v1/lots/{lot_id}/detail_for_edit`

- Upstream: `/api/v1/lots/{lot_id}/detail_for_edit`
- Source: `routers/business/lots.py:get_lot_detail_for_edit`

**Path Parameters**
- `lot_id` (int)

**Query Parameters**
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.order_items`
- `v20.orders`

---

### POST `/apis/mobile/v1/api/v1/lots/{lot_id}/lock`

- Upstream: `/api/v1/lots/{lot_id}/lock`
- Source: `routers/business/lots.py:lock_lot`

**Query Parameters**
- `lot_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.order_items`
- `v20.orders`

---

### POST `/apis/mobile/v1/api/v1/lots/{lot_id}/unlock`

- Upstream: `/api/v1/lots/{lot_id}/unlock`
- Source: `routers/business/lots.py:unlock_lot`

**Query Parameters**
- `lot_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.order_items`
- `v20.orders`

---

## Group: `/api/v1/notifications'

### POST `/apis/mobile/v1/api/v1/notifications/emails/queue`

- Upstream: `/api/v1/notifications/emails/queue`
- Source: `routers/business/notifications.py:queue_email`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/notifications/otp/send`

- Upstream: `/api/v1/notifications/otp/send`
- Source: `routers/business/notifications.py:send_otp`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/orders'

### GET `/apis/mobile/v1/api/v1/orders/`

- Upstream: `/api/v1/orders/`
- Source: `routers/business/orders.py:list_orders`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### POST `/apis/mobile/v1/api/v1/orders/`

- Upstream: `/api/v1/orders/`
- Source: `routers/business/orders.py:create_order`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `id`
- `ok`

---

### POST `/apis/mobile/v1/api/v1/orders/{order_id}/cancel`

- Upstream: `/api/v1/orders/{order_id}/cancel`
- Source: `routers/business/orders.py:cancel_order`

**Query Parameters**
- `order_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/orders/{order_id}/confirm`

- Upstream: `/api/v1/orders/{order_id}/confirm`
- Source: `routers/business/orders.py:confirm_order`

**Query Parameters**
- `order_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/overview'

### GET `/apis/mobile/v1/api/v1/overview/applications`

- Upstream: `/api/v1/overview/applications`
- Source: `routers/business/overview.py:list_applications_overview`

**Query Parameters**
- `project_code` (Optional[str])
- `q` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_scope` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`
- `v20.v_customer_lots_pending_qr`
- `v20.v_order_items_deposit_lot`
- *(+2 more)*

---

### GET `/apis/mobile/v1/api/v1/overview/customers/{customer_id}/orders`

- Upstream: `/api/v1/overview/customers/{customer_id}/orders`
- Source: `routers/business/overview.py:customer_orders_detail`

**Path Parameters**
- `customer_id` (int)

**Query Parameters**
- `project_code` (Optional[str])
- `type` (Optional[str])

**Dependencies**
- `company_scope` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `items`
- `orders`
- `qr_active`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`
- `v20.v_customer_lots_pending_qr`
- `v20.v_order_items_deposit_lot`
- *(+2 more)*

---

### GET `/apis/mobile/v1/api/v1/overview/deposits`

- Upstream: `/api/v1/overview/deposits`
- Source: `routers/business/overview.py:list_deposits_overview`

**Query Parameters**
- `project_code` (Optional[str])
- `q` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_scope` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`
- `v20.v_customer_lots_pending_qr`
- `v20.v_order_items_deposit_lot`
- *(+2 more)*

---

### GET `/apis/mobile/v1/api/v1/overview/summary`

- Upstream: `/api/v1/overview/summary`
- Source: `routers/business/overview.py:list_summary_overview`
- Description: - Danh sách khách của dự án X (hoặc tất cả). - Trả:   + thống kê hồ sơ đã mua/đã dùng/đã hoàn/available theo từng loại   + các lô đã cọc thành công   + các lô đã tạo QR và đang chờ chuyển khoản

**Query Parameters**
- `project_code` (Optional[str])
- `q` (Optional[str])
- `page` (int)
- `size` (int)

**Dependencies**
- `company_scope` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`
- `v20.v_customer_lots_pending_qr`
- `v20.v_order_items_deposit_lot`
- *(+2 more)*

---

## Group: `/api/v1/payments'

### GET `/apis/mobile/v1/api/v1/payments/`

- Upstream: `/api/v1/payments/`
- Source: `routers/business/payments.py:list_payments`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### POST `/apis/mobile/v1/api/v1/payments/qr`

- Upstream: `/api/v1/payments/qr`
- Source: `routers/business/payments.py:create_payment_qr`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`
- `payment_id`
- `qr_url`

---

### POST `/apis/mobile/v1/api/v1/payments/{payment_id}/allocate`

- Upstream: `/api/v1/payments/{payment_id}/allocate`
- Source: `routers/business/payments.py:allocate_payment`

**Query Parameters**
- `payment_id` (int)
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/payments/{payment_id}/refund`

- Upstream: `/api/v1/payments/{payment_id}/refund`
- Source: `routers/business/payments.py:refund_payment`

**Query Parameters**
- `payment_id` (int)
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/projects'

### GET `/apis/mobile/v1/api/v1/projects/`

- Upstream: `/api/v1/projects/`
- Source: `routers/business/projects.py:list_projects`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[str])
- `company_code` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/projects/`

- Upstream: `/api/v1/projects/`
- Source: `routers/business/projects.py:create_project`

**Query Parameters**
- `payload` (Dict[str, Any])
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/by_code/{project_code}`

- Upstream: `/api/v1/projects/by_code/{project_code}`
- Source: `routers/business/projects.py:get_project_by_code`

**Query Parameters**
- `project_code` (str)
- `company_code` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/public`

- Upstream: `/api/v1/projects/public`
- Source: `routers/public/projects_public.py:public_projects`
- Description: Trả danh sách dự án theo company_code.  Fields for Customer Portal UI:   - location   - application_deadline_at + application_deadline_text (DD/MM/YYYY HH:mm)   - deposit_deadline_at + deposit_deadline_text (DD/MM/YYYY HH:mm)   - If deadline is NULL => 'Chưa cấu hình hạn online'

**Query Parameters**
- `company_code` (str)
- `q` (str | None)
- `status` (str | None)
- `page` (int)
- `size` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`

**DB source objects referenced in code (views/tables)**

- `v20.projects`

**Schema (likely row fields) for `v20.projects`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `description` | `text` | `YES` |
| `location` | `text` | `YES` |
| `status` | `text` | `YES` |
| `dossier_account_id` | `bigint` | `YES` |
| `deposit_account_id` | `bigint` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `product_type` | `text` | `YES` |
| `application_deadline_at` | `timestamp with time zone` | `YES` |
| `deposit_deadline_at` | `timestamp with time zone` | `YES` |
| `auction_mode` | `text` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/public-priority`

- Upstream: `/api/v1/projects/public-priority`
- Source: `routers/public/projects_public.py:public_projects_priority`
- Description: Clone endpoint /public nhưng có sort ưu tiên cho Service C:  1) ACTIVE lên trước 2) deposit_deadline còn hạn lên trước (so với NOW theo giờ VN)    - deadline NULL coi như "còn hạn" (đang mở) 3) Deadline càng gần hiện tại càng ưu tiên (ASC theo distance đến now) 4) Fallback theo tên (ổn định)  Lưu ý timezone:   - Dùng NOW() của DB và ép về Asia/Ho_Chi_Minh để so sánh an toàn.   - deposit_deadline_at là timestamptz (khuyến nghị).

**Query Parameters**
- `company_code` (str)
- `q` (str | None)
- `status` (str | None)
- `page` (int)
- `size` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`

**DB source objects referenced in code (views/tables)**

- `v20.projects`

**Schema (likely row fields) for `v20.projects`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `description` | `text` | `YES` |
| `location` | `text` | `YES` |
| `status` | `text` | `YES` |
| `dossier_account_id` | `bigint` | `YES` |
| `deposit_account_id` | `bigint` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `product_type` | `text` | `YES` |
| `application_deadline_at` | `timestamp with time zone` | `YES` |
| `deposit_deadline_at` | `timestamp with time zone` | `YES` |
| `auction_mode` | `text` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_id}`

- Upstream: `/api/v1/projects/{project_id}`
- Source: `routers/business/projects.py:get_project`

**Path Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/projects/{project_id}`

- Upstream: `/api/v1/projects/{project_id}`
- Source: `routers/business/projects.py:update_project`

**Query Parameters**
- `project_id` (int)
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_id}/auction_config`

- Upstream: `/api/v1/projects/{project_id}/auction_config`
- Source: `routers/business/projects.py:get_project_auction_config`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `auction`
- `company_code`
- `id`
- `project_code`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/projects/{project_id}/auction_config`

- Upstream: `/api/v1/projects/{project_id}/auction_config`
- Source: `routers/business/projects.py:update_project_auction_config`
- Description: Update cấu hình phiên đấu giá trong projects.extras.auction  payload:   {     "auction_at": "2026-01-27T08:00:00+07:00" | null,     "province_city": "Ninh Bình" | null,     "venue": "Hội trường ..." | null   }  - Field nào không có trong payload => giữ nguyên field đó. - Field có trong payload và = null => set null (xoá giá trị).

**Query Parameters**
- `project_id` (int)
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/projects/{project_id}/auction_mode`

- Upstream: `/api/v1/projects/{project_id}/auction_mode`
- Source: `routers/business/projects.py:update_project_auction_mode`
- Description: Cập nhật riêng trường auction_mode cho 1 dự án: payload: { "auction_mode": "PER_LOT" | "PER_SQM" }

**Query Parameters**
- `project_id` (int)
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_id}/bid_ticket_config`

- Upstream: `/api/v1/projects/{project_id}/bid_ticket_config`
- Source: `routers/business/projects.py:get_project_bid_ticket_config`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `id`
- `project_code`
- `settings`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/projects/{project_id}/bid_ticket_config`

- Upstream: `/api/v1/projects/{project_id}/bid_ticket_config`
- Source: `routers/business/projects.py:update_project_bid_ticket_config`
- Description: payload:   {     "show_price_step": true|false|null   }  - Không có key => giữ nguyên - null => xoá key để fallback default=true

**Query Parameters**
- `project_id` (int)
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/projects/{project_id}/close`

- Upstream: `/api/v1/projects/{project_id}/close`
- Source: `routers/business/projects.py:close_project`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/api/v1/projects/{project_id}/deadlines`

- Upstream: `/api/v1/projects/{project_id}/deadlines`
- Source: `routers/business/projects.py:get_project_deadlines`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `application_deadline_at`
- `company_code`
- `deposit_deadline_at`
- `id`
- `project_code`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### PUT `/apis/mobile/v1/api/v1/projects/{project_id}/deadlines`

- Upstream: `/api/v1/projects/{project_id}/deadlines`
- Source: `routers/business/projects.py:update_project_deadlines`

**Query Parameters**
- `project_id` (int)
- `payload` (Dict[str, Any])

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/projects/{project_id}/disable`

- Upstream: `/api/v1/projects/{project_id}/disable`
- Source: `routers/business/projects.py:disable_project`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### POST `/apis/mobile/v1/api/v1/projects/{project_id}/enable`

- Upstream: `/api/v1/projects/{project_id}/enable`
- Source: `routers/business/projects.py:enable_project`

**Query Parameters**
- `project_id` (int)

**Dependencies**
- `company_scope` (Any)
- `actor` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

**DB source objects referenced in code (views/tables)**

- `v20.orders`

**Schema (likely row fields) for `v20.orders`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `project_id` | `bigint` | `NO` |
| `customer_id` | `bigint` | `NO` |
| `order_code` | `text` | `YES` |
| `type` | `text` | `NO` |
| `status` | `text` | `NO` |
| `currency` | `text` | `YES` |
| `total_vnd` | `numeric` | `NO` |
| `paid_vnd` | `numeric` | `NO` |
| `paid_at` | `timestamp with time zone` | `YES` |
| `expires_at` | `timestamp with time zone` | `YES` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

## Group: `/api/v1/public/customers'

### POST `/apis/mobile/v1/api/v1/public/customers/check`

- Upstream: `/api/v1/public/customers/check`
- Source: `routers/public/public_customers.py:check_customer`

**Query Parameters**
- `payload` (CustomerCheckRequest)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### POST `/apis/mobile/v1/api/v1/public/customers/{customer_id}/dossier-orders`

- Upstream: `/api/v1/public/customers/{customer_id}/dossier-orders`
- Source: `routers/public/public_customers.py:create_order`

**Query Parameters**
- `customer_id` (int)
- `payload` (CreateOrderRequest)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

## Group: `/api/v1/reconcile'

### POST `/apis/mobile/v1/api/v1/reconcile/bank-statement/upload`

- Upstream: `/api/v1/reconcile/bank-statement/upload`
- Source: `routers/business/reconcile.py:upload_bank_statement`

**JSON Body**
- `payload` (List[Dict[str, Any]])

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `inserted`

**DB source objects referenced in code (views/tables)**

- `v20.companies`
- `v20.customer_lot_deposits`
- `v20.customers`

---

### POST `/apis/mobile/v1/api/v1/reconcile/match`

- Upstream: `/api/v1/reconcile/match`
- Source: `routers/business/reconcile.py:match_btx_payment`

**JSON Body**
- `payment_id` (int)
- `bank_transaction_id` (int)
- `auto_confirm` (bool)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `bank_transaction_id`
- `message`
- `payment_id`

**DB source objects referenced in code (views/tables)**

- `v20.companies`
- `v20.customer_lot_deposits`
- `v20.customers`

---

## Group: `/api/v1/registrations'

### GET `/apis/mobile/v1/api/v1/registrations/`

- Upstream: `/api/v1/registrations/`
- Source: `routers/business/registrations.py:list_registrations`

**Query Parameters**
- `q` (Optional[str])
- `status` (Optional[str])
- `project_code` (Optional[str])

**Dependencies**
- `page_size` (Any)
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

---

### POST `/apis/mobile/v1/api/v1/registrations/`

- Upstream: `/api/v1/registrations/`
- Source: `routers/business/registrations.py:create_registration`

**Query Parameters**
- `payload` (dict)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `id`
- `ok`

---

### POST `/apis/mobile/v1/api/v1/registrations/{reg_id}/approve`

- Upstream: `/api/v1/registrations/{reg_id}/approve`
- Source: `routers/business/registrations.py:approve_registration`

**Query Parameters**
- `reg_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/registrations/{reg_id}/lose`

- Upstream: `/api/v1/registrations/{reg_id}/lose`
- Source: `routers/business/registrations.py:lose_registration`

**Query Parameters**
- `reg_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/registrations/{reg_id}/reject`

- Upstream: `/api/v1/registrations/{reg_id}/reject`
- Source: `routers/business/registrations.py:reject_registration`

**Query Parameters**
- `reg_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

### POST `/apis/mobile/v1/api/v1/registrations/{reg_id}/win`

- Upstream: `/api/v1/registrations/{reg_id}/win`
- Source: `routers/business/registrations.py:win_registration`

**Query Parameters**
- `reg_id` (int)

**Dependencies**
- `company_code` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/api/v1/report/auction-sessions'

### POST `/apis/mobile/v1/api/v1/report/auction-sessions/bid-sheets/selected`

- Upstream: `/api/v1/report/auction-sessions/bid-sheets/selected`
- Source: `routers/business/auction_session_reports.py:get_selected_bid_sheets`
- Description: Nhận items (round_lot_id, customer_id) và trả về list tickets. Sort mặc định: STT_LOT.

**Query Parameters**
- `company_code_q` (Optional[str])

**JSON Body**
- `payload` (BidSheetSelectIn)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.customers`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/report/auction-sessions/round-lots/{round_lot_id}/bid-sheets`

- Upstream: `/api/v1/report/auction-sessions/round-lots/{round_lot_id}/bid-sheets`
- Source: `routers/business/auction_session_reports.py:list_bid_sheets_by_round_lot`
- Description: Trả list tickets (JSON) để Service B render phiếu in. Sort mặc định: STT_LOT (stt -> lot_id).

**Path Parameters**
- `round_lot_id` (int)

**Query Parameters**
- `sort_mode` (str)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.customers`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/report/auction-sessions/rounds/{round_id}/bid-sheets`

- Upstream: `/api/v1/report/auction-sessions/rounds/{round_id}/bid-sheets`
- Source: `routers/business/auction_session_reports.py:list_bid_sheets_by_round`
- Description: Trả list tickets cho toàn bộ round. Sort mặc định: STT_LOT (stt -> lot_id).

**Path Parameters**
- `round_id` (int)

**Query Parameters**
- `sort_mode` (str)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.customers`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/api/v1/report/auction-sessions/sessions/{session_id}/bid-sheets`

- Upstream: `/api/v1/report/auction-sessions/sessions/{session_id}/bid-sheets`
- Source: `routers/business/auction_session_reports.py:list_bid_sheets_by_session`
- Description: Trả list tickets cho toàn bộ session. Sort mặc định: STT_LOT (stt -> lot_id).

**Path Parameters**
- `session_id` (int)

**Query Parameters**
- `sort_mode` (str)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`

**DB source objects referenced in code (views/tables)**

- `v20.auction_session_round_lot_participants`
- `v20.auction_session_round_lots`
- `v20.auction_session_rounds`
- `v20.auction_session_sessions`
- `v20.customers`
- `v20.lots`
- `v20.projects`

---

## Group: `/api/v1/report/bid_tickets'

### GET `/apis/mobile/v1/api/v1/report/bid_tickets/`

- Upstream: `/api/v1/report/bid_tickets/`
- Source: `routers/business/bid_tickets.py:list_bid_ticket_candidates`

**Query Parameters**
- `project_code` (Optional[str])
- `lot_code` (Optional[str])
- `customer_q` (Optional[str])
- `customer_id` (Optional[int])
- `lot_id` (Optional[int])
- `include_excluded` (bool)
- `page` (int)
- `size` (int)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.projects`
- `v20.v_report_bid_customers`
- `v20.v_report_bid_ticket_candidates`
- `v20.v_report_bid_ticket_candidates_auto`

---

### GET `/apis/mobile/v1/api/v1/report/bid_tickets/customers`

- Upstream: `/api/v1/report/bid_tickets/customers`
- Source: `routers/business/bid_tickets.py:list_bid_customers`

**Query Parameters**
- `project_code` (Optional[str])
- `customer_q` (Optional[str])
- `page` (int)
- `size` (int)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.projects`
- `v20.v_report_bid_customers`
- `v20.v_report_bid_ticket_candidates`
- `v20.v_report_bid_ticket_candidates_auto`

---

### GET `/apis/mobile/v1/api/v1/report/bid_tickets/one`

- Upstream: `/api/v1/report/bid_tickets/one`
- Source: `routers/business/bid_tickets.py:get_one_bid_ticket`

**Query Parameters**
- `project_code` (str)
- `lot_id` (int)
- `customer_id` (int)
- `include_excluded` (bool)
- `company_code_q` (Optional[str])

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`

**DB source objects referenced in code (views/tables)**

- `v20.projects`
- `v20.v_report_bid_customers`
- `v20.v_report_bid_ticket_candidates`
- `v20.v_report_bid_ticket_candidates_auto`

---

### POST `/apis/mobile/v1/api/v1/report/bid_tickets/selected`

- Upstream: `/api/v1/report/bid_tickets/selected`
- Source: `routers/business/bid_tickets.py:get_selected_bid_tickets`
- Description: Nhận JSON items (customer_id, lot_id) và trả về list dữ liệu phiếu theo đúng sort_mode. - 1 query duy nhất, không gọi /one N lần. - Sort do A quyết định (không phụ thuộc thứ tự request).

**Query Parameters**
- `company_code_q` (Optional[str])

**JSON Body**
- `payload` (BidTicketSelectIn)

**Dependencies**
- `company_scope` (Any)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `meta`

**DB source objects referenced in code (views/tables)**

- `v20.projects`
- `v20.v_report_bid_customers`
- `v20.v_report_bid_ticket_candidates`
- `v20.v_report_bid_ticket_candidates_auto`

---

## Group: `/api/v1/reports'

### GET `/apis/mobile/v1/api/v1/reports/customers/eligible-lots`

- Upstream: `/api/v1/reports/customers/eligible-lots`
- Source: `routers/business/reports.py:customers_eligible_lots`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/customers/not-eligible-lots`

- Upstream: `/api/v1/reports/customers/not-eligible-lots`
- Source: `routers/business/reports.py:customers_not_eligible_lots`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/dossiers/paid/detail`

- Upstream: `/api/v1/reports/dossiers/paid/detail`
- Source: `routers/business/reports.py:dossiers_paid_detail`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/dossiers/paid/summary-customer`

- Upstream: `/api/v1/reports/dossiers/paid/summary-customer`
- Source: `routers/business/reports.py:dossiers_paid_summary_customer`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/dossiers/paid/totals-by-type`

- Upstream: `/api/v1/reports/dossiers/paid/totals-by-type`
- Source: `routers/business/reports.py:dossiers_paid_totals_by_type`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/lot-deposits/eligible`

- Upstream: `/api/v1/reports/lot-deposits/eligible`
- Source: `routers/business/reports.py:lot_deposits_eligible`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/lot-deposits/not-eligible`

- Upstream: `/api/v1/reports/lot-deposits/not-eligible`
- Source: `routers/business/reports.py:lot_deposits_not_eligible`

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `format` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/view/project-customers-lots-eligible`

- Upstream: `/api/v1/reports/view/project-customers-lots-eligible`
- Source: `routers/business/reports.py:view_project_customers_lots_eligible`
- Description: VIEW: v20.v_report_project_customers_lots_eligible  - Mặc định gom theo cụm khách:     + Tính min(lot_code) của từng customer -> cụm có mã lô nhỏ hơn đứng trước.     + Trong cụm, các lô của khách sắp theo lot_code ASC. - limit: nếu truyền thì LIMIT :limit, nếu không truyền thì lấy hết. - Nếu có quyền PII và expose_phone=true thì trả thêm:     bank_code, bank_name, account_number, account_name

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `customer_cccd` (Optional[str])
- `lot_code` (Optional[str])
- `limit` (Optional[int])
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/view/project-customers-lots-not-enough`

- Upstream: `/api/v1/reports/view/project-customers-lots-not-enough`
- Source: `routers/business/reports.py:view_project_customers_lots_not_enough`
- Description: VIEW: v20.v_report_project_customers_lots_not_enough - Mặc định ORDER BY lot_code ASC, customer_full_name ASC - limit: nếu truyền thì LIMIT :limit, nếu không truyền thì lấy hết - Bổ sung tương tự view đủ điều kiện: trả thêm thông tin bank nếu expose_phone & có PII

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `customer_cccd` (Optional[str])
- `lot_code` (Optional[str])
- `limit` (Optional[int])
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/view/project-dossier-items`

- Upstream: `/api/v1/reports/view/project-dossier-items`
- Source: `routers/business/reports.py:view_project_dossier_items`
- Description: VIEW: v20.v_report_project_customer_dossier_items - Chỉ tính các đơn APPLICATION đã PAID (đã nằm trong view) - company_code lấy từ token (có thể override qua query nếu SUPER) - Mặc định ORDER BY customer_full_name, cccd, order_code - limit: nếu truyền thì LIMIT :limit, nếu không truyền thì lấy hết

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `customer_cccd` (Optional[str])
- `limit` (Optional[int])
- `format` (Optional[str])
- `expose_phone` (bool)

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/view/project-lot-deposit-stats`

- Upstream: `/api/v1/reports/view/project-lot-deposit-stats`
- Source: `routers/business/reports.py:view_project_lot_deposit_stats`
- Description: VIEW: v20.v_report_project_lot_deposit_stats - Mặc định ORDER BY lot_code ASC (như yêu cầu) - limit: nếu truyền thì LIMIT :limit, nếu không truyền thì lấy hết

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `lot_code` (Optional[str])
- `min_customers` (Optional[int])
- `max_customers` (Optional[int])
- `limit` (Optional[int])
- `format` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/view/project-lots-eligible`

- Upstream: `/api/v1/reports/view/project-lots-eligible`
- Source: `routers/business/reports.py:view_project_lots_eligible`
- Description: VIEW: v20.v_report_project_lots_eligible - Chỉ chứa các lô có deposit_customer_count >= 2 (theo view) - Mặc định ORDER BY lot_code ASC - limit: nếu truyền thì LIMIT :limit, nếu không truyền thì lấy hết

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `lot_code` (Optional[str])
- `limit` (Optional[int])
- `format` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

### GET `/apis/mobile/v1/api/v1/reports/view/project-lots-not-eligible`

- Upstream: `/api/v1/reports/view/project-lots-not-eligible`
- Source: `routers/business/reports.py:view_project_lots_not_eligible`
- Description: VIEW: v20.v_report_project_lots_ineligible - Mặc định ORDER BY lot_code ASC - limit: nếu truyền thì LIMIT :limit, nếu không truyền thì lấy hết

**Query Parameters**
- `company` (Optional[str])
- `project` (str)
- `lot_code` (Optional[str])
- `limit` (Optional[int])
- `format` (Optional[str])

**Dependencies**
- `user` (CurrentUser)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `count`
- `items`

**DB source objects referenced in code (views/tables)**

- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.v_customer_eligible_lots`
- `v20.v_customer_not_eligible_lots`
- `v20.v_dossier_paid_detail`
- `v20.v_dossier_paid_summary_customer`
- `v20.v_dossier_paid_totals_by_type`
- `v20.v_lot_deposit_not_eligible`
- *(+7 more)*

---

## Group: `/internal'

### POST `/apis/mobile/v1/internal/dispatch-email-once`

- Upstream: `/internal/dispatch-email-once`
- Source: `routers/internal/email_dispatcher.py:api_dispatch_email_once`
- Description: Trigger thủ công/cron: quét outbox và gửi emails (best-effort). Chỉ SUPER_ADMIN được phép gọi.

**Query Parameters**
- `limit` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `ok`

---

## Group: `/public'

### GET `/apis/mobile/v1/public/__diag/orders-app`

- Upstream: `/public/__diag/orders-app`
- Source: `routers/public/orders_payments.py:diag_orders_app`

**Query Parameters**
- `company_code` (str)
- `project_code` (str)
- `cccd` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `customer`
- `error`
- `notes`
- `order_items_columns`
- `orders_columns`
- `project`
- `trace`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.dossier_types`
- `v20.order_items`
- `v20.orders`
- `v20.payment_qr_requests`
- `v20.projects`

---

### GET `/apis/mobile/v1/public/announcements/{company_code}`

- Upstream: `/public/announcements/{company_code}`
- Source: `routers/public/announcements.py:public_list_announcements`

**Query Parameters**
- `company_code` (str)
- `page` (int)
- `size` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `data`
- `page`
- `size`
- `total`

**DB source objects referenced in code (views/tables)**

- `v20.public_announcements`

**Schema (likely row fields) for `v20.public_announcements`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `title` | `text` | `NO` |
| `summary` | `text` | `YES` |
| `category` | `text` | `YES` |
| `publish_date` | `date` | `YES` |
| `link_url` | `text` | `NO` |
| `pinned` | `boolean` | `NO` |
| `sort_order` | `integer` | `NO` |
| `status` | `USER-DEFINED` | `NO` |
| `starts_at` | `timestamp with time zone` | `YES` |
| `ends_at` | `timestamp with time zone` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |
| `updated_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/public/companies/{company_code}`

- Upstream: `/public/companies/{company_code}`
- Source: `routers/public/company.py:public_get_company`
- Description: Trả về thông tin cơ bản của công ty theo company_code (public). - Đọc từ bảng v20.companies - Các trường phone/email/address lấy từ cột JSON extras nếu có. - Không tìm thấy thì exists=false, các trường còn lại là null (HTTP 200).

**Query Parameters**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.companies`

**Schema (likely row fields) for `v20.companies`**

| field | type | nullable |
|---|---|---|
| `id` | `bigint` | `NO` |
| `company_code` | `text` | `NO` |
| `name` | `text` | `NO` |
| `tax_code` | `text` | `YES` |
| `address` | `text` | `YES` |
| `phone` | `text` | `YES` |
| `email` | `text` | `YES` |
| `is_active` | `boolean` | `NO` |
| `extras` | `jsonb` | `YES` |
| `created_at` | `timestamp with time zone` | `NO` |

---

### GET `/apis/mobile/v1/public/customers/{cccd}/dossier-available`

- Upstream: `/public/customers/{cccd}/dossier-available`
- Source: `routers/public/deposit_public.py:get_customer_dossier_available`
- Description: Lấy số hồ sơ đã mua/đã dùng/còn lại từ VIEW v_customer_dossier_stats (đã được trigger/backfill đồng bộ).

**Query Parameters**
- `cccd` (str)
- `company_code` (str)
- `project_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### POST `/apis/mobile/v1/public/customers/{cccd}/refund-bank`

- Upstream: `/public/customers/{cccd}/refund-bank`
- Source: `routers/public/customer_refund_account.py:set_refund_bank`

**Query Parameters**
- `cccd` (str)

**Headers**
- `idempotency_key` (Optional[str])

**JSON Body**
- `payload` (RefundBankCreateIn)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_bank_accounts`
- `v20.customers`

---

### POST `/apis/mobile/v1/public/orders/application/create`

- Upstream: `/public/orders/application/create`
- Source: `routers/public/orders_payments.py:create_application_order`

**Query Parameters**
- `payload` (CreateApplicationOrderIn)

**Headers**
- `idempotency_key` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.dossier_types`
- `v20.order_items`
- `v20.orders`
- `v20.payment_qr_requests`
- `v20.projects`

---

### POST `/apis/mobile/v1/public/orders/deposit/checkout`

- Upstream: `/public/orders/deposit/checkout`
- Source: `routers/public/deposit_public.py:deposit_checkout`

**JSON Body**
- `company_code` (str)
- `project_code` (str)
- `cccd` (str)
- `lot_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### POST `/apis/mobile/v1/public/orders/deposit/create`

- Upstream: `/public/orders/deposit/create`
- Source: `routers/public/deposit_public.py:deposit_create`

**JSON Body**
- `payload` (DepositCreateIn)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### POST `/apis/mobile/v1/public/orders/deposit/eligibility`

- Upstream: `/public/orders/deposit/eligibility`
- Source: `routers/public/deposit_public.py:check_deposit_eligibility`

**JSON Body**
- `payload` (DepositEligibilityIn)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### GET `/apis/mobile/v1/public/orders/deposit/{order_code}/payment-receipts`

- Upstream: `/public/orders/deposit/{order_code}/payment-receipts`
- Source: `routers/public/deposit_public.py:deposit_payment_receipts`
- Description: Trả danh sách các khoản đã nhận tiền (để khách yên tâm). - Giữ received_at (ISO) để không phá client cũ - Thêm received_at_text (DD/MM/YYYY HH:MM:SS) cho UI thân thiện

**Query Parameters**
- `order_code` (str)
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### GET `/apis/mobile/v1/public/orders/deposit/{order_code}/payment-status`

- Upstream: `/public/orders/deposit/{order_code}/payment-status`
- Source: `routers/public/deposit_public.py:deposit_payment_status`

**Query Parameters**
- `order_code` (str)
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### POST `/apis/mobile/v1/public/orders/deposit/{order_code}/qr`

- Upstream: `/public/orders/deposit/{order_code}/qr`
- Source: `routers/public/deposit_public.py:create_deposit_qr`
- Description: Tạo QR cho đơn DEPOSIT. Đảm bảo order_code theo chuẩn helper: - Nếu bản ghi chưa có order_code (dữ liệu cũ) → tự sinh mã DEP... và cập nhật rồi mới tạo QR.

**Path Parameters**
- `order_code` (str)

**Query Parameters**
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### GET `/apis/mobile/v1/public/orders/{order_code}`

- Upstream: `/public/orders/{order_code}`
- Source: `routers/public/orders_payments.py:get_order_status`

**Query Parameters**
- `order_code` (str)
- `company_code` (str)
- `debug` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.dossier_types`
- `v20.order_items`
- `v20.orders`
- `v20.payment_qr_requests`
- `v20.projects`

---

### POST `/apis/mobile/v1/public/orders/{order_code}/qr`

- Upstream: `/public/orders/{order_code}/qr`
- Source: `routers/public/orders_payments.py:create_order_qr`

**Query Parameters**
- `order_code` (str)
- `company_code` (str)
- `debug` (int)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.dossier_types`
- `v20.order_items`
- `v20.orders`
- `v20.payment_qr_requests`
- `v20.projects`

---

### POST `/apis/mobile/v1/public/payments/webhook`

- Upstream: `/public/payments/webhook`
- Source: `routers/public/orders_payments.py:payment_webhook`

**Query Parameters**
- `payload` (PaymentWebhookIn)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `message`
- `ok`
- `order_code`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.dossier_types`
- `v20.order_items`
- `v20.orders`
- `v20.payment_qr_requests`
- `v20.projects`

---

### GET `/apis/mobile/v1/public/projects/{project_code}/lots`

- Upstream: `/public/projects/{project_code}/lots`
- Source: `routers/public/deposit_public.py:list_project_lots`
- Description: Trả danh sách lô của dự án. - Nếu KHÔNG truyền cccd  -> trả toàn bộ. - Nếu CÓ cccd            -> chỉ trả các lô đủ điều kiện hồ sơ:     Mỗi loại trong required_dossiers của lô phải có available >= qty tương ứng     theo view v20.v_customer_dossier_stats (đúng project).   Đồng thời loại bỏ NHỮNG LÔ KHÁCH ĐÃ CỌC THÀNH CÔNG (v20.v_customer_lots_paid).

**Query Parameters**
- `project_code` (str)
- `company_code` (str)
- `cccd` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

### GET `/apis/mobile/v1/public/projects/{project_code}/lots/{lot_code}`

- Upstream: `/public/projects/{project_code}/lots/{lot_code}`
- Source: `routers/public/deposit_public.py:get_lot_detail`

**Query Parameters**
- `project_code` (str)
- `lot_code` (str)
- `company_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.lots`
- `v20.order_items`
- `v20.order_receipts`
- `v20.orders`
- `v20.projects`
- `v20.v_customer_dossier_stats`
- `v20.v_customer_lots_paid`

---

## Group: `/public/documents'

### POST `/apis/mobile/v1/public/documents/upload`

- Upstream: `/public/documents/upload`
- Source: `routers/public/customer_flow_upload.py:upload_customer_document`
- Description: Upload public:   - CCCD_FRONT / CCCD_BACK: chỉ cần company_code + cccd   - SIGNED_FORM: cần thêm project_code  Trả về:   - upload_id (v20.doc_uploads.id)   - url public (r2.dev / cdn)

**Query Parameters**
- `company_code` (str)
- `cccd` (str)
- `doc_kind` (str)
- `project_code` (Optional[str])
- `file` (UploadFile)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `bucket`
- `company_code`
- `customer_id`
- `doc_kind`
- `mime_type`
- `object_key`
- `ok`
- `project_code`
- `project_id`
- `sha256`
- `size_bytes`
- `upload_id`
- `url`

**DB source objects referenced in code (views/tables)**

- `v20.customers`
- `v20.doc_customer_company_kyc`
- `v20.doc_customer_company_kyc_history`
- `v20.doc_customer_project_documents`
- `v20.doc_customer_project_documents_history`
- `v20.doc_uploads`
- `v20.projects`

---

## Group: `/public/register'

### GET `/apis/mobile/v1/public/register/customers/check`

- Upstream: `/public/register/customers/check`
- Source: `routers/public/customer_flow.py:check_customer`
- Description: Kiểm tra hồ sơ khách hàng công khai.  Rule theo yêu cầu:   - Nếu customer.created_at trong 15 phút gần nhất => trả RAW cho:       customer.phone, customer.email, refund_account.account_number   - Nếu quá 15 phút => mask 3 trường trên bằng '*'   - Các trường khác giữ RAW

**Query Parameters**
- `company_code` (str)
- `cccd` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.dossier_types`
- `v20.lots`
- `v20.projects`

---

### POST `/apis/mobile/v1/public/register/customers/submit`

- Upstream: `/public/register/customers/submit`
- Source: `routers/public/customer_flow.py:submit_customer`
- Description: Upsert công khai:   - Nếu chưa có customer → tạo mới đầy đủ.   - Nếu đã có → chỉ fill các trường đang rỗng (public không ghi đè).   - Trả 409 nếu không trường nào được phép cập nhật thêm.  IMPORTANT:   - Telegram notify chạy background (không block API, không phụ thuộc thành công/thất bại).

**Query Parameters**
- `payload` (SubmitCustomerIn)

**Headers**
- `idempotency_key` (Optional[str])

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.dossier_types`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/public/register/dossier/catalog`

- Upstream: `/public/register/dossier/catalog`
- Source: `routers/public/customer_flow.py:dossier_catalog_public`
- Description: Trả danh mục loại hồ sơ (dossier_types) theo product_type của dự án, CHỈ bao gồm những loại thực sự có ít nhất 1 lô thuộc khoảng giá (min_total_vnd, max_total_vnd) trong dự án đó.  Tương thích nhiều biến thể schema (có/không có 'code', 'unit_price', 'price_vnd', 'is_active').

**Query Parameters**
- `company_code` (str)
- `project_code` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**Top-level keys inside `data` (inferred from Service A return dict)**

- `company_code`
- `items`
- `project_code`
- `project_type`

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.dossier_types`
- `v20.lots`
- `v20.projects`

---

### GET `/apis/mobile/v1/public/register/dossier/quote`

- Upstream: `/public/register/dossier/quote`
- Source: `routers/public/customer_flow.py:dossier_quote`
- Description: Tạm thời trả đơn giá cứng (hoặc có thể đọc từ settings sau này). Logic thanh toán / tạo đơn đã chuyển sang orders_payments.py.

**Query Parameters**
- `company_code` (str)
- `cccd` (str)

**Response (JSON)**

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

**DB source objects referenced in code (views/tables)**

- `v20.banks`
- `v20.customer_bank_accounts`
- `v20.customers`
- `v20.dossier_types`
- `v20.lots`
- `v20.projects`

---

