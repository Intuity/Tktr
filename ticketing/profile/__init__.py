
def includeme(config):
    config.add_route("user_profile","/profile")
    config.add_route("user_profile_edit","/profile/edit")
    config.add_route("user_profile_photo","/profile/photo")
    config.add_route("user_password","/profile/password")
    config.add_route("purchase_agreement_act","/purchase_agreement_action")
    config.add_route("privacy_policy_act","/privacy_policy_action")
    config.add_route("refused_agreement","/refused")
    # Qualify for discount
    config.add_route("discount", "/discount")
    # Guest details
    config.add_route("guest_profile_photo","/profile/photo/{tick_id}")
    config.add_route("guest_info","/guest")
    # Ticket details/edit/transfer
    config.add_route("ticket_details", "/ticket/{tick_id}")
    config.add_route("ticket_payment_history", "/ticket/{tick_id}/history")
    config.add_route("ticket_edit_guest", "/ticket/{tick_id}/edit")
    config.add_route("ticket_edit_guest_pay", "/ticket/{tick_id}/edit/pay")
    config.add_route("ticket_make_mine", "/ticket/{tick_id}/owner")
    config.add_route("transfer_ticket", "/ticket/{tick_id}/transfer")
    config.add_route("transfer_ticket_pay", "/ticket/{tick_id}/transfer/pay")
    config.add_route("ticket_download", "/ticket/{tick_id}/download")
    config.add_route("ticket_download_method", "/ticket/{tick_id}/download/{method}")
    config.add_route("ticket_download_all_method", "/ticket/download/{method}")
    config.add_route("ticket_download_payment_method", "/payment/{payment_id}/download/{method}")
