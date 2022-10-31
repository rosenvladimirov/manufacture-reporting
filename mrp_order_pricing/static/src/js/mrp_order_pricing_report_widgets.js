odoo.define('mrp_order_pricing.mrp_order_pricing_report_widget', function
(require) {
'use strict';

var Widget = require('web.Widget');

return Widget.extend({
    events: {
        'click .o_mrp_order_pricing_action': 'boundLink',
        'click .o_mrp_order_pricing_action_multi': 'boundLinkmulti',
        'click .o_mrp_order_pricing_action_monetary': 'boundLinkMonetary',
        'click .o_mrp_order_pricing_action_monetary_multi': 'boundLinkMonetarymulti',
    },
    init: function () {
        this._super.apply(this, arguments);
    },
    start: function () {
        return this._super.apply(this, arguments);
    },
    boundLink: function (e) {
        var res_model = $(e.target).data('res-model');
        var res_id = $(e.target).data('active-id');
        // console.log("ACTION", res_model, res_id, $(e.target));
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: res_model,
            res_id: res_id,
            views: [[false, 'form']],
            target: 'current'
        });
    },
    boundLinkmulti: function (e) {
        var res_model = $(e.currentTarget).data('res-model');
        var domain = $(e.currentTarget).data('domain');
        var string = $(e.currentTarget).text().replace(/\n|\r/g, '').replace(/\s+/g, '');
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: res_model,
            domain: domain,
            views: [[false, "list"], [false, "form"]],
            name: string,
            flags: {'form': {'action_buttons': true, 'clear_breadcrumbs': true}},
            target: 'current'
        });
    },
    boundLinkMonetary: function (e) {
        var res_model = $(e.target.parentElement).data('res-model');
        var res_id = $(e.target.parentElement).data('active-id');
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: res_model,
            res_id: res_id,
            views: [[false, 'form']],
            target: 'current'
        });
    },
    boundLinkMonetarymulti: function (e) {
        var res_model = $(e.target.parentElement).data('res-model');
        var domain = $(e.target.parentElement).data('domain');
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: res_model,
            domain: domain,
            views: [[false, "list"], [false, "form"]],
            target: 'current'
        });
    },
});

});
