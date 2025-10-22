from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestPurchaseApprovalWorkflow(TransactionCase):

    def setUp(self):
        super().setUp()
        # Create security groups
        self.group_user = self.env.ref('purchase_approval_workflow.group_purchase_user')
        self.group_level1 = self.env.ref('purchase_approval_workflow.group_purchase_approval_level1')
        self.group_level2 = self.env.ref('purchase_approval_workflow.group_purchase_approval_level2')

        # Create users
        self.user_po = self.env['res.users'].create({
            'name': 'Regular User',
            'login': 'regular',
            'groups_id': [(6, 0, [self.group_user.id])],
        })
        self.user_level1 = self.env['res.users'].create({
            'name': 'Level 1 Approver',
            'login': 'level1',
            'groups_id': [(6, 0, [self.group_level1.id])],
        })
        self.user_level2 = self.env['res.users'].create({
            'name': 'Level 2 Approver',
            'login': 'level2',
            'groups_id': [(6, 0, [self.group_level2.id])],
        })

        # Create config
        self.config = self.env['purchase.approval.config'].create({
            'name': 'Default Config',
            'level1_min_amount': 5001,
            'level1_max_amount': 20000,
            'level2_min_amount': 20001,
            'level1_approver_group_id': self.group_level1.id,
            'level2_approver_group_id': self.group_level2.id,
        })

        # Purchase order (default 10,000)
        self.po = self.env['purchase.order'].with_context(test_mode=True).create({
            'partner_id': self.env.ref('base.res_partner_1').id,
            'order_line': [(0, 0, {
                'name': 'Product A',
                'product_qty': 1,
                'price_unit': 10000,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        })

    def test_01_auto_approval(self):
        """P.O. <= 5000 should auto approve"""
        po = self.po.with_context(test_mode=True).copy({
            'order_line': [(0, 0, {
                'name': 'Product B',
                'product_qty': 1,
                'price_unit': 3000,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        })
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_02_level1_required(self):
        """P.O. between 5001 and 20000 goes to to_approve"""
        self.po.button_confirm()
        self.assertEqual(self.po.state, 'to_approve')

    def test_03_level1_approval(self):
        """Level 1 approver approves"""
        self.po.button_confirm()
        self.po = self.po.with_user(self.user_level1).with_context(test_mode=True)
        self.po.action_level1_approve()
        self.assertIn(self.po.state, ['approved_level1', 'purchase'])

    def test_04_level2_approval(self):
        """Level 2 approver finalizes"""
        po = self.po.with_context(test_mode=True).copy({
            'order_line': [(0, 0, {
                'name': 'Product C',
                'product_qty': 1,
                'price_unit': 25000,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        })
        po.button_confirm()
        po = po.with_user(self.user_level1).with_context(test_mode=True)
        po.action_level1_approve()
        po = po.with_user(self.user_level2).with_context(test_mode=True)
        po.action_level2_approve()
        self.assertEqual(po.state, 'purchase')

    def test_05_rejection(self):
        """Rejection sends P.O. back to draft"""
        self.po.button_confirm()
        self.po.action_reject()
        self.assertEqual(self.po.state, 'draft')

    def test_06_different_amounts(self):
        """Workflow respects thresholds"""
        # 4999 auto approve
        po1 = self.po.copy({
            'order_line': [(0, 0, {
                'name': 'Test',
                'product_qty': 1,
                'price_unit': 4999,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        }).with_context(test_mode=True)
        po1.button_confirm()
        self.assertEqual(po1.state, 'purchase')

        # 10,000 needs level1
        po2 = self.po.copy({
            'order_line': [(0, 0, {
                'name': 'Test',
                'product_qty': 1,
                'price_unit': 10000,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        }).with_context(test_mode=True)
        po2.button_confirm()
        self.assertEqual(po2.state, 'to_approve')

        # 25,000 needs level2
        po3 = self.po.copy({
            'order_line': [(0, 0, {
                'name': 'Test',
                'product_qty': 1,
                'price_unit': 25000,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        }).with_context(test_mode=True)
        po3.button_confirm()
        self.assertEqual(po3.state, 'to_approve')

    def test_07_no_config(self):
        """If no config, approvals fall back to auto-approval"""
        self.config.unlink()
        po = self.po.copy({
            'order_line': [(0, 0, {
                'name': 'Product D',
                'product_qty': 1,
                'price_unit': 15000,
                'product_id': self.env.ref('product.product_product_4').id,
                'date_planned': '2025-09-29',
            })],
        }).with_context(test_mode=True)
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')
