from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    state = fields.Selection(selection_add=[
        ('to_approve', 'To Approve'),
        ('approved_level1', 'Approved Level 1'),
        ('approved_level2', 'Approved Level 2')
    ], ondelete={
        'to_approve': 'cascade',
        'approved_level1': 'cascade', 
        'approved_level2': 'cascade'
    })
    
    approval_level = fields.Integer(string='Approval Level', compute='_compute_approval_level', store=True)
    requires_approval = fields.Boolean(string='Requires Approval', compute='_compute_requires_approval')
    level1_approver_id = fields.Many2one('res.users', string='Level 1 Approver')
    level2_approver_id = fields.Many2one('res.users', string='Level 2 Approver')
    level1_approval_date = fields.Datetime(string='Level 1 Approval Date')
    level2_approval_date = fields.Datetime(string='Level 2 Approval Date')
    
    @api.depends('amount_total')
    def _compute_approval_level(self):
        for order in self:
            config = self.env['purchase.approval.config'].search([
                ('company_id', '=', order.company_id.id),
                ('active', '=', True)
            ], limit=1)
            
            if not config:
                order.approval_level = 0
                continue
                
            amount = order.amount_total
            if amount <= 5000:
                order.approval_level = 0  # Auto-approve
            elif config.level1_min_amount <= amount <= config.level1_max_amount:
                order.approval_level = 1
            elif amount >= config.level2_min_amount:
                order.approval_level = 2
            else:
                raise ValidationError(_("The purchase order amount %s does not fall into any configured approval range.") % amount)
    
    @api.depends('approval_level')
    def _compute_requires_approval(self):
        for order in self:
            order.requires_approval = order.approval_level > 0
    
    def button_confirm(self):
        """Override confirm button to implement approval workflow"""
        orders_requiring_approval = self.env['purchase.order']
        orders_for_normal_flow = self.env['purchase.order']
        
        for order in self:
            # Ensure approval level is computed
            order._compute_approval_level()
            
            if order.requires_approval and order.state in ['draft', 'sent']:
                orders_requiring_approval |= order
            else:
                orders_for_normal_flow |= order
        
        # Handle orders requiring approval
        if orders_requiring_approval:
            orders_requiring_approval.write({'state': 'to_approve'})
            for order in orders_requiring_approval:
                order._send_approval_email()
        
        # Handle orders that don't require approval using the normal flow
        if orders_for_normal_flow:
            # Call the parent button_confirm for these orders
            result = super(PurchaseOrder, orders_for_normal_flow).button_confirm()
        
        # If we have both types, we need to return something meaningful
        if orders_requiring_approval and not orders_for_normal_flow:
            return True
        elif orders_for_normal_flow:
            return result
        
        return True
    
    def action_level1_approve(self):
        """Level 1 approval action"""
        if not self._check_approval_rights(1):
            raise UserError(_('You do not have permission to approve Level 1 purchases.'))
        
        for order in self:
            if order.approval_level >= 1:
                if order.approval_level == 1:
                    # Final approval for level 1
                    order.write({
                        'state': 'purchase',
                        'level1_approver_id': self.env.user.id,
                        'level1_approval_date': fields.Datetime.now()
                    })
                    if not self.env.context.get('test_mode'):
                        order.message_post(
                            body=_("Purchase Order approved at level 1 by %s") % self.env.user.name
                        )
                else:
                    # Move to level 2 approval
                    order.write({
                        'state': 'approved_level1',
                        'level1_approver_id': self.env.user.id,
                        'level1_approval_date': fields.Datetime.now()
                    })
                    if not self.env.context.get('test_mode'):
                        order.message_post(
                            body=_("Purchase Order approved at level 1 by %s, pending level 2 approval") % self.env.user.name
                        )
                        order._send_approval_email(level=2)
        return True
    
    def action_level2_approve(self):
        """Level 2 approval action"""
        if not self._check_approval_rights(2):
            raise UserError(_('You do not have permission to approve Level 2 purchases.'))
        
        for order in self:
            if order.approval_level == 2:
                order.write({
                    'state': 'purchase',
                    'level2_approver_id': self.env.user.id,
                    'level2_approval_date': fields.Datetime.now()
                })
                if not self.env.context.get('test_mode'):
                    order.message_post(
                        body=_("Purchase Order approved at level 2 by %s") % self.env.user.name
                    )
        return True

    
    def action_reject(self):
        """Reject purchase order"""
        for order in self:
            order.write({'state': 'draft'})
            if not self.env.context.get('test_mode'):
                order.message_post(
                    body=_("Purchase Order rejected by %s") % self.env.user.name
                )
                order._send_rejection_email()
        return True
    
    def _check_approval_rights(self, level):
        """Check if user has approval rights for the given level"""
        config = self.env['purchase.approval.config'].search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            return False
            
        if level == 1 and config.level1_approver_group_id:
            return self.env.user in config.level1_approver_group_id.users
        elif level == 2 and config.level2_approver_group_id:
            return self.env.user in config.level2_approver_group_id.users
        
        return False
    
    def _send_approval_email(self, level=1):
        """Send approval notification email"""
        if self.env.context.get('test_mode'):
            # skip sending emails in tests
            return
        
        template = self.env.ref('purchase_approval_workflow.email_approval_level1', raise_if_not_found=False)
        if level == 2:
            template = self.env.ref('purchase_approval_workflow.email_approval_level2', raise_if_not_found=False)
        
        for order in self:
            if template:
                template.with_context(level=level).send_mail(order.id, force_send=True)
    
    def _send_rejection_email(self):
        """Send rejection notification email"""
        if self.env.context.get('test_mode'):
            # skip sending emails in tests
            return
        template = self.env.ref('purchase_approval_workflow.email_rejection')
        for order in self:
            if template:
                template.send_mail(order.id, force_send=True)