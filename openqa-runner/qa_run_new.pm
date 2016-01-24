# SUSE's openQA tests
#
# Copyright © 2009-2013 Bernhard M. Wiedemann
# Copyright © 2012-2016 SUSE LLC
#
# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty provided the copyright
# notice and this notice are preserved.  This file is offered as-is,
# without any warranty.

package qa_run;
use base "opensusebasetest";
use testapi;

sub create_qaset_config() {
    my $self = shift;
    my @list = $self->test_run_list();
    return unless @list;
    assert_script_run "echo 'SQ_TEST_RUN_LIST=(\n " . join("\n ", @list) . "\n )' > /root/qaset/config";
}

sub test_run_list() {
    return ();
}

sub junit_type() {
    die "you need to overload junit_type in your class";
}

sub test_suite() {
    die "you need to overload test_suite in your class";
}

# qa_testset_automation validation test
sub run() {
    my $self = shift;

    assert_screen "inst-bootmenu", 30;
    send_key "ret";    # boot

    assert_screen "grub2", 15;
    send_key "ret";

    assert_screen "text-login", 50;
    type_string "root\n";
    assert_screen "password-prompt", 10;
    type_password;
    type_string "\n";
    sleep 1;

    # remove SLES
    assert_script_run "zypper rr 1";
    # remove SDK
    assert_script_run "zypper rr 1";

    my $repo = get_var('HOST') . "/assets/repo/" . get_var('REPO_0');
    assert_script_run "zypper -n ar -f $repo sles";
    $repo = get_var('HOST') . "/assets/repo/" . get_var('REPO_1');
    assert_script_run "zypper -n ar -f $repo sdk";

    # Add Repo - http://dist.nue.suse.com/ibs/QA:/Head/SLE-12-SP1/
    assert_script_run "zypper --no-gpg-check -n ar -f " . get_var('QA_HEAD_REPO') . " qa_ibs";

    # refresh repo
    assert_script_run "zypper --gpg-auto-import-keys ref -r qa_ibs";

    # Install - zypper in qa_testset_automation
    assert_script_run "zypper -n in qa_testset_automation";

    assert_script_run "mkdir /root/qaset";
    $self->create_qaset_config();

    # Trigger run script
    my $script          = sprintf("/usr/share/qa/qaset/run/%s-run", $self->test_suite());
    my $log_dir         = "/var/log/qaset/log";
    my $submission_dir  = "/var/log/qaset/submission";
    my $upload_url      = autoinst_url();
    my $junit_type      = $self->junit_type();
    my $junit_file      = "/tmp/junit.xml";
    assert_script_run "/usr/share/qa/qaset/bin/openqa_runner.py -u '$upload_url' -l $log_dir -s $submission_dir $script";

    # output the QADB link
    type_string "grep -E \"http://.*/submission.php.*submission_id=[0-9]+\"  /var/log/qaset/submission/submission-*.log " . "| awk -F\": \"  '{print \$2}' | tee -a /dev/$serialdev\n";

    # test junit
    my $junit_type = $self->junit_type();
    assert_script_run "/usr/share/qa/qaset/bin/junit_xml_gen.py /var/log/qaset/log -s /var/log/qaset/submission -o /tmp/junit.xml -n '$junit_type'";
    assert_script_run "ls -l /tmp/";
    parse_junit_log("/tmp/junit.xml");
}

sub test_flags {
    return {important => 1};
}

1;

