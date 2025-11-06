from odoo import http
from odoo.http import request


class HmsPublicController(http.Controller):

    @http.route('/hms/patient/register', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def patient_registration(self, **post):
        errors = {}
        countries = request.env['res.country'].sudo().search([])

        if request.httprequest.method == 'POST':
            # --- validation ---
            if not post.get('name'):
                errors['name'] = 'Full name is required.'

            if post.get('email'):
                existing = request.env['res.partner'].sudo().search(
                    [('email', '=', post.get('email'))], limit=1
                )
                if existing:
                    errors['email'] = 'Email already registered.'

            # --- create partner if no errors ---
            if not errors:
                country_id = post.get('country_id')
                partner = request.env['res.partner'].sudo().create({
                    'name': post.get('name'),
                    'email': post.get('email'),
                    'phone': post.get('phone'),
                    'street': post.get('street'),
                    'city': post.get('city'),
                    'country_id': int(country_id) if country_id and country_id.isdigit() else False,
                    'is_patient': True,
                    'outsider_patient': True,
                })

                # ------------------------------------------------------------
                # Create portal user & send activation email
                # ------------------------------------------------------------
                PortalWizard = request.env['portal.wizard'].sudo().create({
                    'partner_ids': [(6, 0, [partner.id])],
                })
                # This internally calls _send_email() and sends the welcome mail
                PortalWizard.user_ids[0].action_grant_access()

                return request.render(
                    'hms.hms_patient_register_success',
                    {'partner': partner}
                )

        # GET or validation errors → re-render form
        return request.render('hms.hms_patient_register_template', {
            'post': post,
            'errors': errors,
            'countries': countries,
        })