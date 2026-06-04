from __future__ import annotations

from typing import Any


def get_shopify_app_recommendations() -> dict[str, Any]:
    """
    A small curated list of useful Shopify App Store links.

    Note: These are external links (Shopify App Store). We keep the catalog here so it
    can be reused by public pages and vendor settings without duplicating the list.
    """

    apps = [
        {
            "name": "Shiprocket",
            "badge": "SR",
            "meta": "Shipping • India",
            "desc": "Courier partners, shipping labels, tracking, and COD workflows for Indian sellers.",
            "tags": ["shipping", "india", "cod"],
            "url": "https://apps.shopify.com/shiprocket",
        },
        {
            "name": "AfterShip",
            "badge": "AS",
            "meta": "Order Tracking • WISMO",
            "desc": "Branded tracking page + notifications to reduce “Where is my order?” queries.",
            "tags": ["shipping", "tracking", "support"],
            "url": "https://apps.shopify.com/aftership",
        },
        {
            "name": "Klaviyo",
            "badge": "KL",
            "meta": "Email • SMS • WhatsApp",
            "desc": "Email + SMS marketing automation, segmentation, and abandoned cart flows.",
            "tags": ["marketing", "email", "sms"],
            "url": "https://apps.shopify.com/klaviyo-email-marketing",
        },
        {
            "name": "Omnisend",
            "badge": "OM",
            "meta": "Email • SMS • Popups",
            "desc": "Marketing automation with templates, popups, and ready-made workflows.",
            "tags": ["marketing", "email", "sms", "cro"],
            "url": "https://apps.shopify.com/omnisend",
        },
        {
            "name": "Judge.me",
            "badge": "JM",
            "meta": "Reviews • UGC",
            "desc": "Collect and display product reviews, ratings, photos/videos, and testimonials.",
            "tags": ["reviews", "ugc", "cro"],
            "url": "https://apps.shopify.com/judgeme",
        },
        {
            "name": "Loox",
            "badge": "LX",
            "meta": "Photo Reviews • Social Proof",
            "desc": "Visual photo/video reviews + widgets to boost conversion and trust.",
            "tags": ["reviews", "ugc", "cro"],
            "url": "https://apps.shopify.com/loox",
        },
        {
            "name": "Tidio",
            "badge": "TD",
            "meta": "Live Chat • AI Chatbot",
            "desc": "Live chat + chatbot to support shoppers and improve conversion.",
            "tags": ["support", "chat", "cro"],
            "url": "https://apps.shopify.com/tidio-chat",
        },
        {
            "name": "Gorgias",
            "badge": "GG",
            "meta": "Helpdesk • Chat • Support",
            "desc": "Centralize email + chat + social support in one helpdesk built for ecommerce brands.",
            "tags": ["support", "helpdesk", "chat"],
            "url": "https://apps.shopify.com/helpdesk",
        },
        {
            "name": "PageFly",
            "badge": "PF",
            "meta": "Landing Pages • CRO",
            "desc": "Build landing/product pages with drag-and-drop sections and templates.",
            "tags": ["cro", "pagebuilder", "marketing"],
            "url": "https://apps.shopify.com/pagefly",
        },
    ]

    categories = [
        {
            "title": "Shipping Solutions",
            "subtitle": "Orders & Shipping",
            "tag": "shipping",
            "url": "https://apps.shopify.com/categories/orders-and-shipping-shipping-solutions",
        },
        {
            "title": "Sales Channels",
            "subtitle": "Sell on marketplaces & social",
            "tag": "category",
            "url": "https://apps.shopify.com/categories/sales-channels",
        },
        {
            "title": "Marketing",
            "subtitle": "Email, SMS, automation, popups",
            "tag": "marketing",
            "url": "https://apps.shopify.com/categories/marketing-and-conversion-marketing",
        },
        {
            "title": "Reviews & UGC",
            "subtitle": "Social proof widgets",
            "tag": "reviews",
            "url": "https://apps.shopify.com/categories/marketing-and-conversion-product-reviews",
        },
        {
            "title": "Customer Support",
            "subtitle": "Chat + helpdesk",
            "tag": "support",
            "url": "https://apps.shopify.com/categories/customer-support-customer-support",
        },
        {
            "title": "Page Builders",
            "subtitle": "Landing pages & CRO",
            "tag": "cro",
            "url": "https://apps.shopify.com/categories/store-design-page-builder",
        },
    ]

    return {"apps": apps, "categories": categories}

