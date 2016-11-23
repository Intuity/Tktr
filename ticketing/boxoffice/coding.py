import hashlib, datetime, base64, math, random, re, string, time

class Coding(object):

    check_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    # "withdash" toggles whether the blocks of 4 characters are spaced by dashes
    # "short" toggles whether the code is 8 characters in length (short) or 16 (long)
    def generateUniqueCode(self, withdash=True, short=False):
        unique_code = ""
        # Get the epoch time
        epoch = str(int(time.mktime(time.gmtime())))
        # Must generate a unique code!
        base_str = self.genRandomString(size=10) + datetime.datetime.now().strftime("%Y-%m-%d,%H:%M:%S") + self.genRandomString(size=10)
        unique_code = base64.urlsafe_b64encode(hashlib.md5(base_str).digest())
        unique_code = re.sub(r"[^A-Za-z0-9]", "", unique_code)
        return_code = ""
        # First digits really don't vary enough to include them
        epoch = epoch[4:]
        # Fill the epoch up to 16 chars
        before = int(math.floor((16 - len(epoch)) / 2.0))
        after = 16 - len(epoch) - before
        return_code = (unique_code[:before] + epoch + unique_code[-after:]).upper()
        # Add the check digit
        return_code = return_code[:15] + self.getCheckDigit(return_code[:15])
        if withdash:
            return_code = "%s-%s-%s-%s" % (return_code[:4], return_code[4:8], return_code[8:12], return_code[12:16])
        if short and withdash:
            return_code = return_code[0:5] + return_code[15:19]
        elif short and not withdash:
            return_code = return_code[0:4] + return_code[12:17]
        # Before passing back ensure we don't have any indistinguishable characters
        return_code = return_code.replace('2', 'Z').replace('5', 'S').replace('1','I').replace('O','0')
        return return_code

    def genRandomString(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for x in range(size))

    def getCheckDigit(self, raw_string):
        full_sum = sum(bytearray(raw_string))
        return Coding.check_chars[full_sum % len(Coding.check_chars)]
