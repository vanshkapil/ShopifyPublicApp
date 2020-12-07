import uuid
import os
import json
import logging
import smtplib

from flask import Flask, redirect, request, render_template,jsonify

import helpers
from shopify_client import ShopifyStoreClient

from config import WEBHOOK_APP_UNINSTALL_URL

app = Flask(__name__)


ACCESS_TOKEN = None
NONCE = None
ACCESS_MODE = []  # Defaults to offline access mode if left blank or omitted. https://shopify.dev/concepts/about-apis/authentication#api-access-modes
SCOPES = ['write_script_tags']  # https://shopify.dev/docs/admin-api/access-scopes


data_dict = {}

def mail(email,body):
    server = smtplib.SMTP('smtp-mail.outlook.com',587)
    server.ehlo()
    server.starttls()
    server.ehlo()

    user = "vanshkapil@hotmail.co.uk"
    password = "BABA@sai987"
    to_addr = email
    Subject = "Welcome! Your AI chatbot is getting ready... "
    Body = body
    server.login(user,password)



    msg = f"Subject: {Subject}\n\n {Body}"

    server.sendmail(
        user,
        to_addr,
        msg

    )

    print('Mail sent', msg)
    server.quit()


#background process happening without any refreshing
@app.route('/handle_data', methods=['POST'])
def handle_data():

    result = request.form
    name = result.get('name')
    email = result.get('email')
    data_dict.update({'name': name})
    data_dict.update({'email': email})
    print(data_dict)

    if name and email:
        emailBody = f'Dear {name}, \n Thanks for choosing to work with Sundaybots. \n\n As you know you have chosen a conversational AI chatbot, which is customized for your business. \n We would need to understand your taste and gather some information about your business. \n\n Kindly click on the link below to book a quick call with us at a time convenient to you. \n https://calendly.com/sundaybots/30min \n\n Vansh Kapil \n Founder \n Team Sundaybots'
        mail(email,emailBody)
        returnmsg = 'Thank you. Please check your email for more details.'

        return jsonify({'name': returnmsg})

    return jsonify({'error': 'Missing data!'})

@app.route('/app_launched', methods=['GET'])
@helpers.verify_web_call
def app_launched():
    shop = request.args.get('shop')
    global ACCESS_TOKEN, NONCE

    if ACCESS_TOKEN:
        return render_template('welcome.html', shop=shop)

    # The NONCE is a single-use random value we send to Shopify so we know the next call from Shopify is valid (see #app_installed)
    #   https://en.wikipedia.org/wiki/Cryptographic_nonce
    NONCE = uuid.uuid4().hex
    redirect_url = helpers.generate_install_redirect_url(shop=shop, scopes=SCOPES, nonce=NONCE, access_mode=ACCESS_MODE)
    return redirect(redirect_url, code=302)


@app.route('/app_installed', methods=['GET'])
@helpers.verify_web_call
def app_installed():
    state = request.args.get('state')
    global NONCE, ACCESS_TOKEN

    # Shopify passes our NONCE, created in #app_launched, as the `state` parameter, we need to ensure it matches!
    if state != NONCE:
        return "Invalid `state` received", 400
    NONCE = None

    # Ok, NONCE matches, we can get rid of it now (a nonce, by definition, should only be used once)
    # Using the `code` received from Shopify we can now generate an access token that is specific to the specified `shop` with the
    #   ACCESS_MODE and SCOPES we asked for in #app_installed
    shop = request.args.get('shop')
    code = request.args.get('code')
    ACCESS_TOKEN = ShopifyStoreClient.authenticate(shop=shop, code=code)

    # We have an access token! Now let's register a webhook so Shopify will notify us if/when the app gets uninstalled
    # NOTE This webhook will call the #app_uninstalled function defined below
    shopify_client = ShopifyStoreClient(shop=shop, access_token=ACCESS_TOKEN)
    shopify_client.create_webhook(address=WEBHOOK_APP_UNINSTALL_URL, topic="app/uninstalled")

    redirect_url = helpers.generate_post_install_redirect_url(shop=shop)
    return redirect(redirect_url, code=302)


@app.route('/app_uninstalled', methods=['POST'])
@helpers.verify_webhook_call
def app_uninstalled():
    # https://shopify.dev/docs/admin-api/rest/reference/events/webhook?api[version]=2020-04
    # Someone uninstalled your app, clean up anything you need to
    # NOTE the shop ACCESS_TOKEN is now void!
    global ACCESS_TOKEN
    ACCESS_TOKEN = None

    webhook_topic = request.headers.get('X-Shopify-Topic')
    webhook_payload = request.get_json()
    logging.error(f"webhook call received {webhook_topic}:\n{json.dumps(webhook_payload, indent=4)}")

    return "OK"


@app.route('/data_removal_request', methods=['POST'])
@helpers.verify_webhook_call
def data_removal_request():
    # https://shopify.dev/tutorials/add-gdpr-webhooks-to-your-app
    # Clear all personal information you may have stored about the specified shop
    return "OK"


if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)