{
    "name": "Purchase Approval Workflow",
    "version": "1.0",
    "summary": "Three-Level Approval Workflow for Purchases",
    "category": "Purchases",
    "author": "Custom Dev",
    "depends": ["purchase", "mail"],
    "data": [
        "security/purchase_approval_groups.xml",
        "security/ir.model.access.csv",
        "data/mail_templates.xml",
        "views/approval_config_views.xml",
        "views/purchase_order_view.xml", 
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}