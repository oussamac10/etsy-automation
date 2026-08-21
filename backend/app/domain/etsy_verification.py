"""Domain model and pure comparison logic for Post-Dispatch Etsy Draft Verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EtsyVerificationCheckStatus(StrEnum):
    SYNCED = "synced"
    DIFFERENT = "different"
    MISSING = "missing"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"
    NOT_APPLICABLE = "not_applicable"


class EtsyOverallVerificationStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_ATTENTION = "needs_attention"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EtsyVerificationCheck:
    key: str
    label: str
    category: str  # "listing", "commerce", "media_and_delivery", "attributes", "manual_review"
    status: EtsyVerificationCheckStatus
    expected: Any = None
    actual: Any = None
    message: str | None = None
    source: str = "etsy_api"
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "status": self.status.value if isinstance(self.status, EtsyVerificationCheckStatus) else str(self.status),
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
            "source": self.source,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class EtsyVerificationSummary:
    synced: int = 0
    warnings: int = 0
    errors: int = 0
    manual_review: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "synced": self.synced,
            "warnings": self.warnings,
            "errors": self.errors,
            "manual_review": self.manual_review,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class EtsyDraftVerification:
    workflow_id: str
    listing_id: str | None
    status: EtsyOverallVerificationStatus
    verified_at: datetime
    summary: EtsyVerificationSummary
    checks: list[EtsyVerificationCheck] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "listing_id": self.listing_id,
            "status": self.status.value if isinstance(self.status, EtsyOverallVerificationStatus) else str(self.status),
            "verified_at": self.verified_at.isoformat(),
            "summary": self.summary.to_dict(),
            "checks": [c.to_dict() for c in self.checks],
            "error_message": self.error_message,
        }


def _normalize_text(text: str) -> str:
    """Normalize multiline text for comparison across HTTP and API encoding transformations."""
    if not text:
        return ""
    import html

    t = html.unescape(text)
    # Normalize CRLF and CR to LF
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # Replace non-breaking spaces with standard spaces
    t = t.replace("\xa0", " ")
    # Strip trailing whitespace on each line
    lines = [line.rstrip() for line in t.split("\n")]
    # Strip leading and trailing empty lines
    return "\n".join(lines).strip()


def compare_etsy_draft(

    *,
    workflow_id: str,
    listing_id: str,
    # Local expected values from ListingDraft
    expected_title: str,
    expected_description: str,
    expected_tags: list[str],
    expected_price_minor: int | None,
    expected_currency: str,
    expected_quantity: int,
    expected_sku: str | None,
    expected_taxonomy_id: int | None,
    expected_taxonomy_path: str | None,
    expected_shop_section_id: str | None,
    expected_shop_section_name: str | None,
    expected_should_auto_renew: bool,
    expected_properties: dict[str, Any],
    expected_mockup_count: int,
    expected_file_count: int,
    expected_filenames: list[str],
    expected_ai_disclosure: str | None,
    expected_shopping_cart_summary: str | None,
    # Actual fetched data from Etsy Open API v3
    actual_listing: dict[str, Any] | None,
    actual_inventory: dict[str, Any] | None,
    actual_images: list[dict[str, Any]] | None,
    actual_files: list[dict[str, Any]] | None,
    actual_properties: list[dict[str, Any]] | None,
    fetch_error: str | None = None,
) -> EtsyDraftVerification:
    """Pure domain comparison between local expected state and remote Etsy OpenAPI v3 state."""
    now = datetime.now(UTC)

    if fetch_error or actual_listing is None:
        summary = EtsyVerificationSummary(errors=1, total=1)
        return EtsyDraftVerification(
            workflow_id=workflow_id,
            listing_id=listing_id,
            status=EtsyOverallVerificationStatus.FAILED,
            verified_at=now,
            summary=summary,
            checks=[
                EtsyVerificationCheck(
                    key="listing_connection",
                    label="Etsy Listing Retrieval",
                    category="listing",
                    status=EtsyVerificationCheckStatus.FAILED,
                    expected={"listing_id": listing_id},
                    actual=None,
                    message=fetch_error or "Could not fetch listing details from Etsy Open API v3.",
                    source="etsy_api",
                )
            ],
            error_message=fetch_error or "Could not fetch listing details from Etsy Open API v3.",
        )

    checks: list[EtsyVerificationCheck] = []

    # 1. State / Draft Check
    actual_state = str(actual_listing.get("state", "draft")).lower()
    if actual_state == "draft":
        checks.append(
            EtsyVerificationCheck(
                key="draft_state",
                label="Listing State",
                category="listing",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected="draft",
                actual="draft",
                message="Draft (Safe) in Etsy Shop Manager.",
            )
        )
    else:
        checks.append(
            EtsyVerificationCheck(
                key="draft_state",
                label="Listing State",
                category="listing",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected="draft",
                actual=actual_state,
                message=f"Listing state on Etsy is '{actual_state}' (expected 'draft').",
            )
        )

    # 2. Title
    actual_title_raw = str(actual_listing.get("title", ""))
    actual_title_norm = _normalize_text(actual_title_raw)
    exp_title_norm = _normalize_text(expected_title)
    if actual_title_norm == exp_title_norm:
        checks.append(
            EtsyVerificationCheck(
                key="title",
                label="Title",
                category="listing",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected=expected_title,
                actual=actual_title_raw.strip(),
            )
        )
    else:
        checks.append(
            EtsyVerificationCheck(
                key="title",
                label="Title",
                category="listing",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=expected_title,
                actual=actual_title_raw.strip(),
                message="Title on Etsy differs from expected title.",
            )
        )

    # 3. Description
    actual_desc_raw = str(actual_listing.get("description", ""))
    actual_desc_norm = _normalize_text(actual_desc_raw)
    exp_desc_norm = _normalize_text(expected_description)
    if actual_desc_norm == exp_desc_norm:
        checks.append(
            EtsyVerificationCheck(
                key="description",
                label="Description",
                category="listing",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected="Exact match",
                actual="Exact match",
            )
        )
    else:
        checks.append(
            EtsyVerificationCheck(
                key="description",
                label="Description",
                category="listing",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=exp_desc_norm[:200] + ("..." if len(exp_desc_norm) > 200 else ""),
                actual=actual_desc_norm[:200] + ("..." if len(actual_desc_norm) > 200 else ""),
                message="Description on Etsy differs from local listing description.",
            )
        )


    # 4. Tags (Case-normalized, order-insensitive)
    raw_actual_tags = actual_listing.get("tags") or []
    actual_tags_list = [str(t).strip() for t in raw_actual_tags if t]
    actual_tags_lower = {t.lower(): t for t in actual_tags_list}
    expected_tags_lower = {t.lower(): t for t in expected_tags}

    missing_tags = [expected_tags_lower[k] for k in expected_tags_lower if k not in actual_tags_lower]
    unexpected_tags = [actual_tags_lower[k] for k in actual_tags_lower if k not in expected_tags_lower]

    tag_count = len(actual_tags_list)
    exp_tag_count = len(expected_tags)

    if not missing_tags and not unexpected_tags:
        checks.append(
            EtsyVerificationCheck(
                key="tags",
                label="Tags",
                category="listing",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected=f"{exp_tag_count} / {exp_tag_count} tags",
                actual=f"{tag_count} / {exp_tag_count} tags",
                details={"tags": actual_tags_list},
            )
        )
    else:
        matched_count = exp_tag_count - len(missing_tags)
        checks.append(
            EtsyVerificationCheck(
                key="tags",
                label="Tags",
                category="listing",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=f"{exp_tag_count} tags",
                actual=f"{matched_count} / {exp_tag_count} matched",
                message=f"{len(missing_tags)} missing, {len(unexpected_tags)} unexpected on Etsy.",
                details={
                    "missing": missing_tags,
                    "unexpected": unexpected_tags,
                    "actual_tags": actual_tags_list,
                },
            )
        )

    # 5. Category / Taxonomy
    actual_tax_id = actual_listing.get("taxonomy_id")
    if expected_taxonomy_id is not None:
        if actual_tax_id == expected_taxonomy_id:
            checks.append(
                EtsyVerificationCheck(
                    key="category",
                    label="Category",
                    category="listing",
                    status=EtsyVerificationCheckStatus.SYNCED,
                    expected=f"{expected_taxonomy_id} ({expected_taxonomy_path or 'Digital'})",
                    actual=f"{actual_tax_id} ({expected_taxonomy_path or 'Digital'})",
                )
            )
        else:
            checks.append(
                EtsyVerificationCheck(
                    key="category",
                    label="Category",
                    category="listing",
                    status=EtsyVerificationCheckStatus.DIFFERENT,
                    expected=f"{expected_taxonomy_id} ({expected_taxonomy_path or 'Expected'})",
                    actual=f"{actual_tax_id or 'None'}",
                    message=f"Etsy taxonomy ID is {actual_tax_id} (expected {expected_taxonomy_id}).",
                )
            )

    # 6. Price & Currency
    actual_price_obj = actual_listing.get("price") or {}
    # Etsy price object has amount, divisor, currency_code
    actual_amount = actual_price_obj.get("amount")
    actual_divisor = actual_price_obj.get("divisor", 100) or 100
    actual_curr = actual_price_obj.get("currency_code", "USD")

    if actual_amount is not None and expected_price_minor is not None:
        # Convert actual to minor units: actual_amount * (100 / divisor) or matching divisor
        actual_minor = int(round(actual_amount * (100.0 / actual_divisor)))
        exp_fmt = f"{expected_price_minor / 100:.2f} {expected_currency}"
        act_fmt = f"{actual_minor / 100:.2f} {actual_curr}"

        if actual_minor == expected_price_minor and actual_curr.upper() == expected_currency.upper():
            checks.append(
                EtsyVerificationCheck(
                    key="price",
                    label="Price",
                    category="commerce",
                    status=EtsyVerificationCheckStatus.SYNCED,
                    expected=exp_fmt,
                    actual=act_fmt,
                )
            )
        else:
            checks.append(
                EtsyVerificationCheck(
                    key="price",
                    label="Price",
                    category="commerce",
                    status=EtsyVerificationCheckStatus.DIFFERENT,
                    expected=exp_fmt,
                    actual=act_fmt,
                    message=f"Price or currency mismatch: expected {exp_fmt}, actual {act_fmt}.",
                )
            )
    elif expected_price_minor is not None:
        checks.append(
            EtsyVerificationCheck(
                key="price",
                label="Price",
                category="commerce",
                status=EtsyVerificationCheckStatus.MISSING,
                expected=f"{expected_price_minor / 100:.2f} {expected_currency}",
                actual="None",
                message="Price data could not be read from Etsy listing payload.",
            )
        )

    # 7. Quantity & SKU (check from listing or inventory)
    actual_qty = actual_listing.get("quantity")
    actual_sku: str | None = None

    if actual_inventory and "products" in actual_inventory:
        prods = actual_inventory.get("products") or []
        if prods:
            p0 = prods[0]
            actual_sku = p0.get("sku")
            offerings = p0.get("offerings") or []
            if offerings:
                actual_qty = offerings[0].get("quantity", actual_qty)

    # Verify Quantity
    if actual_qty == expected_quantity:
        checks.append(
            EtsyVerificationCheck(
                key="quantity",
                label="Quantity",
                category="commerce",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected=expected_quantity,
                actual=actual_qty,
            )
        )
    else:
        checks.append(
            EtsyVerificationCheck(
                key="quantity",
                label="Quantity",
                category="commerce",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=expected_quantity,
                actual=actual_qty,
                message=f"Quantity on Etsy is {actual_qty} (expected {expected_quantity}).",
            )
        )

    # Verify SKU
    if expected_sku:
        if actual_sku == expected_sku or (actual_sku is None and actual_listing.get("sku") == expected_sku):
            checks.append(
                EtsyVerificationCheck(
                    key="sku",
                    label="SKU",
                    category="commerce",
                    status=EtsyVerificationCheckStatus.SYNCED,
                    expected=expected_sku,
                    actual=expected_sku,
                )
            )
        else:
            resolved_act_sku = actual_sku or actual_listing.get("sku")
            checks.append(
                EtsyVerificationCheck(
                    key="sku",
                    label="SKU",
                    category="commerce",
                    status=EtsyVerificationCheckStatus.DIFFERENT if resolved_act_sku else EtsyVerificationCheckStatus.MISSING,
                    expected=expected_sku,
                    actual=resolved_act_sku or "None",
                    message=f"SKU on Etsy is '{resolved_act_sku}' (expected '{expected_sku}').",
                )
            )

    # 8. Shop Section
    actual_section_id = actual_listing.get("shop_section_id")
    actual_sec_str = str(actual_section_id) if actual_section_id is not None and str(actual_section_id) != "0" else None
    exp_sec_str = str(expected_shop_section_id) if expected_shop_section_id is not None and str(expected_shop_section_id) != "0" else None
    has_expected_section = bool(exp_sec_str or (expected_shop_section_name and expected_shop_section_name.strip()))

    if not has_expected_section and not actual_sec_str:
        checks.append(
            EtsyVerificationCheck(
                key="shop_section",
                label="Shop Section",
                category="commerce",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected="None",
                actual="None",
            )
        )
    elif exp_sec_str and actual_sec_str and exp_sec_str == actual_sec_str:
        checks.append(
            EtsyVerificationCheck(
                key="shop_section",
                label="Shop Section",
                category="commerce",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected=expected_shop_section_name or f"Section #{exp_sec_str}",
                actual=expected_shop_section_name or f"Section #{actual_sec_str}",
            )
        )
    elif expected_shop_section_name and actual_sec_str and (not exp_sec_str or not exp_sec_str.isdigit()):
        checks.append(
            EtsyVerificationCheck(
                key="shop_section",
                label="Shop Section",
                category="commerce",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected=expected_shop_section_name,
                actual=expected_shop_section_name,
            )
        )
    elif has_expected_section and not actual_sec_str:
        checks.append(
            EtsyVerificationCheck(
                key="shop_section",
                label="Shop Section",
                category="commerce",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=expected_shop_section_name or f"Section #{exp_sec_str}",
                actual="None on Etsy",
                message=f"Expected shop section '{expected_shop_section_name or exp_sec_str}' but Etsy listing has no section assigned.",
            )
        )
    else:
        checks.append(
            EtsyVerificationCheck(
                key="shop_section",
                label="Shop Section",
                category="commerce",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=expected_shop_section_name or f"Section #{exp_sec_str}",
                actual=f"Section #{actual_sec_str}" if actual_sec_str else "None on Etsy",
                message="Shop section on Etsy differs from expected section.",
            )
        )


    # 9. Renewal
    actual_renew = actual_listing.get("should_auto_renew", False)
    if bool(actual_renew) == bool(expected_should_auto_renew):
        renew_label = "Automatic" if expected_should_auto_renew else "Manual"
        checks.append(
            EtsyVerificationCheck(
                key="renewal",
                label="Renewal",
                category="commerce",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected=renew_label,
                actual=renew_label,
            )
        )
    else:
        exp_renew_label = "Automatic" if expected_should_auto_renew else "Manual"
        act_renew_label = "Automatic" if actual_renew else "Manual"
        checks.append(
            EtsyVerificationCheck(
                key="renewal",
                label="Renewal",
                category="commerce",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected=exp_renew_label,
                actual=act_renew_label,
                message=f"Renewal option on Etsy is {act_renew_label} (expected {exp_renew_label}).",
            )
        )

    # 10. How It's Made / Production Metadata
    who_made = actual_listing.get("who_made", "i_did")
    when_made = actual_listing.get("when_made", "2020_2026")
    item_type = actual_listing.get("listing_type") or actual_listing.get("item_type", "download")
    is_supply = actual_listing.get("is_supply", False)

    is_made_synced = (
        who_made == "i_did"
        and item_type in ("download", "both")
        and not is_supply
    )
    if is_made_synced:
        checks.append(
            EtsyVerificationCheck(
                key="item_metadata",
                label="How It's Made",
                category="listing",
                status=EtsyVerificationCheckStatus.SYNCED,
                expected="I did (2020-2026), Digital Download, Finished Product",
                actual="I did, Digital Download, Finished Product",
            )
        )
    else:
        checks.append(
            EtsyVerificationCheck(
                key="item_metadata",
                label="How It's Made",
                category="listing",
                status=EtsyVerificationCheckStatus.DIFFERENT,
                expected="I did, Digital Download, Finished Product",
                actual=f"Who: {who_made}, Type: {item_type}, Supply: {is_supply}",
                message="Listing origin metadata differs from standard digital download requirements.",
            )
        )

    # 11. Mockups / Images
    act_img_count = len(actual_images or [])
    image_items = [
        {
            "image_id": str(img.get("listing_image_id", "")),
            "rank": img.get("rank", idx + 1),
            "url": img.get("url"),
        }
        for idx, img in enumerate(actual_images or [])
    ]
    if expected_mockup_count > 0:
        if act_img_count >= expected_mockup_count:
            checks.append(
                EtsyVerificationCheck(
                    key="mockups",
                    label="Mockups",
                    category="media_and_delivery",
                    status=EtsyVerificationCheckStatus.SYNCED,
                    expected=f"{expected_mockup_count} uploaded",
                    actual=f"{act_img_count} verified on Etsy",
                    details={"images_count": act_img_count, "images": image_items},
                )
            )
        elif act_img_count > 0:
            checks.append(
                EtsyVerificationCheck(
                    key="mockups",
                    label="Mockups",
                    category="media_and_delivery",
                    status=EtsyVerificationCheckStatus.DIFFERENT,
                    expected=f"{expected_mockup_count} uploaded",
                    actual=f"{act_img_count} verified",
                    message=f"Only {act_img_count} of {expected_mockup_count} expected mockup images exist on Etsy.",
                    details={"images_count": act_img_count, "images": image_items},
                )
            )
        else:
            checks.append(
                EtsyVerificationCheck(
                    key="mockups",
                    label="Mockups",
                    category="media_and_delivery",
                    status=EtsyVerificationCheckStatus.MISSING,
                    expected=f"{expected_mockup_count} uploaded",
                    actual="0 images",
                    message="No mockup images found on Etsy listing.",
                    details={"images_count": 0, "images": []},
                )
            )

    # 12. Digital Files
    act_file_count = len(actual_files or [])
    if expected_file_count > 0:
        actual_filenames = [str(f.get("filename", "")) for f in (actual_files or []) if f.get("filename")]
        if act_file_count >= expected_file_count:
            checks.append(
                EtsyVerificationCheck(
                    key="digital_files",
                    label="Digital Files",
                    category="media_and_delivery",
                    status=EtsyVerificationCheckStatus.SYNCED,
                    expected=f"{expected_file_count} attached",
                    actual=f"{act_file_count} verified on Etsy",
                    details={
                        "actual_filenames": actual_filenames,
                        "expected_filenames": expected_filenames,
                    },
                )
            )
        elif act_file_count > 0:
            checks.append(
                EtsyVerificationCheck(
                    key="digital_files",
                    label="Digital Files",
                    category="media_and_delivery",
                    status=EtsyVerificationCheckStatus.DIFFERENT,
                    expected=f"{expected_file_count} attached",
                    actual=f"{act_file_count} attached",
                    message=f"Only {act_file_count} of {expected_file_count} digital download files attached to Etsy draft.",
                    details={
                        "actual_filenames": actual_filenames,
                        "expected_filenames": expected_filenames,
                    },
                )
            )
        else:
            checks.append(
                EtsyVerificationCheck(
                    key="digital_files",
                    label="Digital Files",
                    category="media_and_delivery",
                    status=EtsyVerificationCheckStatus.MISSING,
                    expected=f"{expected_file_count} attached",
                    actual="0 attached",
                    message="No digital deliverable files found attached to Etsy draft.",
                )
            )

    # 13. Category Attributes / Properties & Materials
    expected_props = expected_properties or {}
    actual_props_map: dict[int, list[str]] = {}
    actual_props_names: dict[int, str] = {}

    if actual_properties:
        for p in actual_properties:
            pid_raw = p.get("property_id")
            if pid_raw is not None:
                try:
                    p_int = int(pid_raw)
                    raw_v = p.get("values") or []
                    actual_props_map[p_int] = [str(v) for v in raw_v if v is not None]
                    if p.get("property_name"):
                        actual_props_names[p_int] = str(p["property_name"])
                except ValueError:
                    pass

    # If Etsy listing returns top-level materials array, map it to common Material property IDs
    raw_materials = actual_listing.get("materials")
    if isinstance(raw_materials, list) and raw_materials:
        mat_strings = [str(m) for m in raw_materials if m]
        # Common Etsy Material property IDs: 148789511893 (digital/graphics), 148789511892, etc.
        for common_mat_pid in (148789511893, 148789511892, 506):
            if common_mat_pid not in actual_props_map or not actual_props_map[common_mat_pid]:
                actual_props_map[common_mat_pid] = mat_strings
                actual_props_names[common_mat_pid] = "Materials"

    total_expected_props = len(expected_props)
    if total_expected_props > 0:
        matched_props = 0
        prop_details: list[dict[str, Any]] = []
        diff_summaries: list[str] = []

        for p_id_str, val in expected_props.items():
            try:
                pid = int(p_id_str)
            except ValueError:
                continue

            # Extract expected values and property display name
            prop_name: str | None = None
            if isinstance(val, dict):
                prop_name = val.get("property_name") or val.get("name") or val.get("display_name")
                if "values" in val and isinstance(val["values"], list):
                    exp_vals = [str(v) for v in val["values"] if v is not None]
                elif "value" in val and val["value"] is not None:
                    exp_vals = [str(val["value"])]
                else:
                    exp_vals = []
            elif isinstance(val, list):
                exp_vals = [str(v) for v in val if v is not None]
            elif val is not None:
                exp_vals = [str(val)]
            else:
                exp_vals = []

            resolved_name = prop_name or actual_props_names.get(pid) or f"Property #{pid}"

            # If this is materials property (e.g. 148789511893) and actual_props_map is empty, check raw materials
            act_vals = list(actual_props_map.get(pid, []))
            if not act_vals and "material" in resolved_name.lower() and isinstance(raw_materials, list):
                act_vals = [str(m) for m in raw_materials if m]

            exp_norm = {v.lower().strip(): v for v in exp_vals if v.strip()}
            act_norm = {a.lower().strip(): a for a in act_vals if a.strip()}

            missing_on_etsy = [orig for key, orig in exp_norm.items() if key not in act_norm]
            extra_on_etsy = [orig for key, orig in act_norm.items() if key not in exp_norm]

            if set(exp_norm.keys()) == set(act_norm.keys()) and exp_norm:
                matched_props += 1
                prop_details.append({
                    "property_id": pid,
                    "property_name": resolved_name,
                    "status": "synced",
                    "expected": exp_vals,
                    "actual": act_vals,
                })
            elif act_vals:
                diff_msg = f"{resolved_name} (Missing on Etsy: {', '.join(missing_on_etsy)})" if missing_on_etsy else f"{resolved_name} differs"
                diff_summaries.append(diff_msg)
                prop_details.append({
                    "property_id": pid,
                    "property_name": resolved_name,
                    "status": "different",
                    "expected": exp_vals,
                    "actual": act_vals,
                    "missing": missing_on_etsy,
                    "unexpected": extra_on_etsy,
                })
            else:
                diff_summaries.append(f"{resolved_name} (missing completely on Etsy)")
                prop_details.append({
                    "property_id": pid,
                    "property_name": resolved_name,
                    "status": "missing",
                    "expected": exp_vals,
                    "actual": [],
                    "missing": exp_vals,
                })

        if matched_props == total_expected_props:
            checks.append(
                EtsyVerificationCheck(
                    key="attributes",
                    label="Category Attributes & Materials",
                    category="attributes",
                    status=EtsyVerificationCheckStatus.SYNCED,
                    expected=f"{total_expected_props} / {total_expected_props} configured",
                    actual=f"{matched_props} / {total_expected_props} verified on Etsy",
                    details={"properties": prop_details},
                )
            )
        else:
            diff_text = "; ".join(diff_summaries[:3])
            checks.append(
                EtsyVerificationCheck(
                    key="attributes",
                    label="Category Attributes & Materials",
                    category="attributes",
                    status=EtsyVerificationCheckStatus.DIFFERENT,
                    expected=f"{total_expected_props} configured",
                    actual=f"{matched_props} / {total_expected_props} verified on Etsy",
                    message=f"{total_expected_props - matched_props} attribute(s) differ on Etsy: {diff_text}.",
                    details={"properties": prop_details},
                )
            )

    # 14. Manual Review Items (Fields NOT available in Etsy Public Open API v3)
    # AI Creation Disclosure
    checks.append(
        EtsyVerificationCheck(
            key="ai_disclosure",
            label="AI Creation Disclosure",
            category="manual_review",
            status=EtsyVerificationCheckStatus.MANUAL_REVIEW,
            expected="Created with an AI generator",
            actual="Review in Etsy web editor",
            message="Etsy requires manual disclosure in Shop Manager ('Created with an AI generator'). Not writable via public API.",
            source="manual_review",
            details={"configured_disclosure": expected_ai_disclosure},
        )
    )

    # Shopping Cart Summary (Etsy Web Editor optional field - not supported in Etsy OpenAPI v3)
    if expected_shopping_cart_summary:
        checks.append(
            EtsyVerificationCheck(
                key="shopping_cart_summary",
                label="Shopping Cart Summary",
                category="listing",
                status=EtsyVerificationCheckStatus.MANUAL_REVIEW,
                expected=f"{len(expected_shopping_cart_summary)}/200 chars",
                actual="Etsy Web Editor",
                message=expected_shopping_cart_summary,
                source="listing_draft",
                details={"shopping_cart_summary": expected_shopping_cart_summary},
            )
        )

    # Primary Thumbnail Crop
    checks.append(
        EtsyVerificationCheck(
            key="thumbnail_crop",
            label="Primary Thumbnail Crop",
            category="manual_review",
            status=EtsyVerificationCheckStatus.MANUAL_REVIEW,
            expected="Centered square crop",
            actual="Review in Etsy web editor",
            message="Inspect and adjust primary mockup thumbnail crop positioning in Etsy Shop Manager.",
            source="manual_review",
        )
    )

    # Tally Summary
    synced_count = sum(1 for c in checks if c.status == EtsyVerificationCheckStatus.SYNCED)
    warnings_count = sum(1 for c in checks if c.status in (EtsyVerificationCheckStatus.DIFFERENT, EtsyVerificationCheckStatus.MISSING))
    errors_count = sum(1 for c in checks if c.status == EtsyVerificationCheckStatus.FAILED)
    manual_count = sum(1 for c in checks if c.status == EtsyVerificationCheckStatus.MANUAL_REVIEW)

    overall_status = EtsyOverallVerificationStatus.VERIFIED
    if errors_count > 0:
        overall_status = EtsyOverallVerificationStatus.FAILED
    elif warnings_count > 0:
        overall_status = EtsyOverallVerificationStatus.NEEDS_ATTENTION

    summary = EtsyVerificationSummary(
        synced=synced_count,
        warnings=warnings_count,
        errors=errors_count,
        manual_review=manual_count,
        total=len(checks),
    )

    return EtsyDraftVerification(
        workflow_id=workflow_id,
        listing_id=listing_id,
        status=overall_status,
        verified_at=now,
        summary=summary,
        checks=checks,
    )
