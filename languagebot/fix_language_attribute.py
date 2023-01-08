"""Reformat language keys in Editions"""
import gzip
import requests

from enum import Enum, auto, unique
from olclient.bots import AbstractBotJob


@unique
class FailureMode(Enum):
    FIELD_NAME = auto()  # the field name is wrong
    STRING = auto()  # key value is a string not a list of dicts
    LANGUAGE_CODE = auto()  # invalid language code


class LanguageBot(AbstractBotJob):
    def __init__(self, *args, **kwargs):
        self.VALID_ATTR_NAME = 'languages'
        self.INVALID_ATTR_NAME = 'language'
        valid_language_code_url = "https://openlibrary.org/query.json?type=/type/language&key=&limit=10000"
        self.VALID_LANGUAGE_DICTS = tuple(requests.get(valid_language_code_url).json())
        self.VALID_LANGUAGE_CODES = list()
        for _lang_dicts in self.VALID_LANGUAGE_DICTS:
            self.VALID_LANGUAGE_CODES.append(_lang_dicts['key'].split('/')[-1])
        self.VALID_LANGUAGE_CODES = tuple(self.VALID_LANGUAGE_CODES)
        super(LanguageBot, self).__init__(*args, **kwargs)

    def fix_languages(self, failure_modes: list, languages: dict) -> list:
        """
        Attempts to mend the language attribute of an Open Library Edition. Does nothing for non-trivial failure modes.
        :param languages: dictionary containing the language attribute(s) of an Open Library Edition
        :param failure_modes: how the languages parameter is faulty
        """
        key_name = self.INVALID_ATTR_NAME if FailureMode.FIELD_NAME in failure_modes else self.VALID_ATTR_NAME
        old_language_value = languages[key_name]
        fixed_languages = []

        if FailureMode.STRING in failure_modes:
            fixed_languages = [old_language_value]
            for language_code in languages.values():
                if language_code in self.VALID_LANGUAGE_CODES:
                    fixed_languages.append({"key": f"/{self.VALID_ATTR_NAME}/{language_code}"})

        if FailureMode.LANGUAGE_CODE in failure_modes:
            fixed_languages = old_language_value
            [fixed_languages.append(language_dict) for language_dict in languages.values()]
        return fixed_languages or old_language_value

    def get_failure_modes(self, languages: dict) -> list:
        """
        Return human-readable failure mode(s).
        :param languages: The result of self.get_languages
        """
        failure_modes = []
        found_string = False
        all_valid = True
        found_attr_name = False
        for attr_name, language in languages.items():
            if not found_attr_name and attr_name != self.VALID_ATTR_NAME:
                failure_modes.append(FailureMode.FIELD_NAME)
                found_attr_name = True

            if not found_string and isinstance(language, str):
                failure_modes.append(FailureMode.STRING)
                found_string = True

            if isinstance(language, list):
                language_list = language
                for lang in language_list:
                    if lang not in self.VALID_LANGUAGE_DICTS:
                        # i.e  "/languages/foobar"'
                        failure_modes.append(FailureMode.LANGUAGE_CODE)
                        all_valid = False
                    if not all_valid:
                        break
        return failure_modes

    def get_languages(self, obj) -> dict:
        """
        Returns dict with values equal to the language attribute of an Open Library Edition.
        The dictionary key is the name of the attribute the language value was found on the Edition.
        :param obj: A JSON dictionary or Open Library Edition
        """
        if isinstance(obj, dict):
            lang_dict = {self.VALID_ATTR_NAME: obj.get(self.VALID_ATTR_NAME),
                         self.INVALID_ATTR_NAME: obj.get(self.INVALID_ATTR_NAME)}
        else:
            lang_dict = {self.VALID_ATTR_NAME: getattr(obj, self.VALID_ATTR_NAME, None),
                         self.INVALID_ATTR_NAME: getattr(obj, self.INVALID_ATTR_NAME, None)}
        lang_dict = {k: v for k, v in lang_dict.items() if v is not None}  # don't store non-existent attributes
        return lang_dict

    def are_languages_valid(self, languages: dict) -> bool:
        """
        :param languages: dict containing language attribute data of an OpenLibrary Edition
        :returns bool:
        """
        if self.get_failure_modes(languages):
            # if any failure modes are found than the 'languages' argument is not valid
            return False
        return True

    def run(self) -> None:
        """
        Properly format the language attribute. Proper format is '"languages": [{"key": "/languages/<language code>"}]'
        """
        self.dry_run_declaration()
        comment = 'reformat language attribute'
        with gzip.open(self.args.file, 'rb') as fin:
            for row_num, row in enumerate(fin):
                row, json_data = self.process_row(row)
                old_languages = self.get_languages(json_data)
                if not old_languages or self.are_languages_valid(old_languages):
                    continue

                olid = json_data['key'].split('/')[-1]
                edition = self.ol.Edition.get(olid)
                old_languages = self.get_languages(edition)
                if not old_languages or self.are_languages_valid(old_languages):
                    continue

                invalid_attr_name, valid_attr_name = self.INVALID_ATTR_NAME, self.VALID_ATTR_NAME
                failure_modes = self.get_failure_modes(old_languages)
                if not failure_modes:
                    continue

                setattr(edition, self.VALID_ATTR_NAME, self.fix_languages(failure_modes, old_languages))
                if old_languages != edition.languages or FailureMode.FIELD_NAME in failure_modes:
                    msg = f"{edition.olid}\t'{old_languages}\t'{valid_attr_name}:' {edition.languages}"
                    self.logger.info(msg)
                    self.save(lambda: edition.save(comment=comment))


if __name__ == "__main__":
    bot = LanguageBot()

    try:
        bot.run()
    except Exception as e:
        bot.logger.exception("")
        raise e
