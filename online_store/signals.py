"""
Signal hooks for the Online Store.

Currently a no-op stub; kept so the project can later hook in
``post_save`` listeners on ``Vendor`` and ``VendorProductListing`` (e.g. to
invalidate the public directory cache) without having to introduce a new
``AppConfig.ready`` body in the future.
"""
