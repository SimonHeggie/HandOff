import unittest
from unittest.mock import patch
from conversion_policy import capabilities,automatic_eligible

class CapabilityPolicy(unittest.TestCase):
    def test_matrix_covers_brief_and_distinguishes_validation(self):
        rows=capabilities();self.assertEqual(len(rows),62)
        for feature in ('linear_gradient','radial_gradient','gp_instances','external_link','glow','rig'):
            row=rows[feature]
            self.assertTrue(all(key in row for key in ('psd_format_support','photoshop_support',
                'photocraft_support','psd_writer','photoshop_validation','photocraft_validation')))
        self.assertEqual(rows['linear_gradient']['photoshop_support'],'supported')
        self.assertEqual(rows['linear_gradient']['photoshop_validation'],'unverified')

    def test_unverified_native_mappings_stay_out_of_native_conversion(self):
        for target in ('photoshop','photocraft'):
            for feature in ('gp_instances','linear_gradient','radial_gradient'):
                self.assertFalse(automatic_eligible(feature,target))

    def test_validation_of_one_editor_does_not_enable_another(self):
        row=dict(capabilities()['linear_gradient'],psd_writer='implemented',
            reader_validation='passed',photoshop_validation='passed',photocraft_validation='unverified')
        with patch('conversion_policy.capabilities',return_value={'linear_gradient':row}):
            self.assertTrue(automatic_eligible('linear_gradient','photoshop'))
            self.assertFalse(automatic_eligible('linear_gradient','photocraft'))
            row['reader_validation']='unverified'
            self.assertFalse(automatic_eligible('linear_gradient','photoshop'))
