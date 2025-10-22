from odoo import models, fields, api

class PurchaseApprovalConfig(models.Model):
    _name = 'purchase.approval.config'
    _description = 'Purchase Approval Configuration'
    
    name = fields.Char(string='Name', required=True)
    level1_min_amount = fields.Float(string='Level 1 Minimum Amount', default=5001.0)
    level1_max_amount = fields.Float(string='Level 1 Maximum Amount', default=20000.0)
    level2_min_amount = fields.Float(string='Level 2 Minimum Amount', default=20001.0)
    level1_approver_group_id = fields.Many2one(
        'res.groups', 
        string='Level 1 Approver Group',
        domain="[('category_id', '=', category_id)]"
    )
    level2_approver_group_id = fields.Many2one(
        'res.groups', 
        string='Level 2 Approver Group',
        domain="[('category_id', '=', category_id)]"
    )
    category_id = fields.Many2one(
        'ir.module.category',
        string='Category',
        default=lambda self: self.env.ref('purchase_approval_workflow.module_category_purchase_approval').id
    )
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)