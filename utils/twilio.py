#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import time

# Twilio configuration give numbers as '+13234823951'
toNumber = '<CELL_PHONE_HERE>'
fromNumber = '<TWILIO_NUMBER_GOES_HERE>'
accountSid = '<ACCOUNT_SID_GOES_HERE>'
authToken = '<AUTH_TOKEN_GOES_HERE>'
client = Client(accountSid, authToken)

# Successful Purchase COMPLETED!!!
print('Order Placed!')
try:
    client.messages.create(to=toNumber, from_=fromNumber, body='ORDER PLACED!')
except (NameError, TwilioRestException):
    pass
    for i in range(3):
        print('\a')
        time.sleep(1)
    time.sleep(1800)
    driver.quit()
    return
