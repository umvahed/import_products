# -*- coding: utf-8 -*-
{
    "name": "Import Products and Variants with Stock",
    "author": "Warlock Technologies Pvt Ltd.",
    "website": "http://warlocktechnologies.com",
    "description": """
Import Products
====================================

This module Import Products And Variants With Stock.
    """,
    "summary": """Import Products And Variants With Stock""",
    "version": "16.0.1.0",
    "price": 30.00,
    "currency": "USD",
    "support": "support@warlocktechnologies.com",
    "category": "Product",
    "license": "OPL-1",
    "sequence": 1,
    "description": """
This module allows to Import Product and Variants with Qty.
=========================================================================
    """,
    "depends": ["stock"],
    "images": ["images/screen_image.png"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/import_product_view.xml",
    ],
    "installable": True,
}
