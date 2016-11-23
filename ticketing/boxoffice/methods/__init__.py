def includeme(config):
    # Original Payments
    config.add_route("pay_stripe", "/stripe")
    config.add_route("pay_collegebill", "/collegebill")
    config.add_route("pay_banktransfer", "/banktransfer")
    config.add_route("pay_cheque", "/cheque")
    # Alterations
    config.add_route("alter_pay_stripe", "/{payment_id}/stripe")
    config.add_route("alter_pay_collegebill", "/{payment_id}/collegebill")
    config.add_route("alter_pay_banktransfer", "/{payment_id}/banktransfer")
    config.add_route("alter_pay_cheque", "/{payment_id}/cheque")
